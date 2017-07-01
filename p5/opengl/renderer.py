#
# Part of p5: A Python package based on Processing
# Copyright (C) 2017 Abhik Pal
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
"""The OpenGL renderer for p5."""

import builtins
from ctypes import *
import math

from pyglet.gl import *

from ..tmp import Matrix4
from .shader import Shader
from .shader import ShaderProgram
from .shader import fragment_default
from .shader import vertex_default

# Geometry cache for the renderer
#
# Regenerating buffers and binding them to arrays can get very
# expensive. We use this dictionary to cache the shape the fist time
# its drawn and reuse the information if the same shape is asked to be
# drawn again.
#
_geometries = {}

_shader_program = ShaderProgram()

# All user transformations are stored in these matrices. We send off
# the matrix data as uniforms while rendering a shape.
#
transform_matrix = Matrix4()
modelview_matrix = Matrix4()
projection_matrix = Matrix4()

background_color = (0.8, 0.8, 0.8, 1.0)
fill_color = (1.0, 1.0, 1.0, 1.0)
stroke_color = (0, 0, 0, 1.0)
fill_enabled = True
stroke_enabled = True

def initialize(gl_version):
    """Initialize the OpenGL renderer.

    For an OpenGL based renderer this sets up the viewport and creates
    the shader program.

    """
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)
    glViewport(0, 0, builtins.width, builtins.height)

    shaders = [
        Shader(vertex_default, 'vertex', version=gl_version),
        Shader(fragment_default, 'fragment', version=gl_version),
    ]

    for shader in shaders:
        shader.compile()
        _shader_program.attach(shader)

    _shader_program.link()
    _shader_program.activate()

    _shader_program.add_uniform('fill_color', 'vec4')
    _shader_program.add_uniform('projection', 'mat4')
    _shader_program.add_uniform('view', 'mat4')
    _shader_program.add_uniform('model', 'mat4')

    reset_view()
    clear()

def cleanup():
    """Run the clean-up routine for the renderer"""
    pass

def clear():
    """Use the background color to clear the screen."""
    glClearColor(*background_color)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

def reset_view():
    """Reset the view of the renderer.
    """
    global transform_matrix
    global modelview_matrix
    global projection_matrix

    cz = (builtins.height / 2) / math.tan(math.radians(30))
    projection = Matrix4.new_perspective(
        math.radians(60),
        builtins.width / builtins.height,
        0.1 * cz,
        10 * cz
    )
    view = Matrix4().translate(-builtins.width/2, -builtins.height/2, -cz)

    transform_matrix = Matrix4()
    modelview_matrix = view
    projection_matrix =  projection

    _shader_program['model'] =  transform_matrix
    _shader_program['view'] = modelview_matrix
    _shader_program['projection'] = projection

def pre_render():
    global transform_matrix
    transform_matrix = Matrix4()
    _shader_program['model'] = transform_matrix
    _shader_program['view'] = modelview_matrix
    _shader_program['projection'] = projection_matrix

def post_render():
    pass

def render(shape):
    """Use the renderer to render a Shape.

    :param shape: The shape to be rendered.
    :type shape: Shape
    """

    #
    # TODO (abhikpal, 2017-06-10)
    #
    # - Ideally, this should be implemented by the Shape's
    #   __hash__ so that we can use the shape itself as the dict
    #   key and get rid of this str(__dict__(...) business.
    #
    # TODO (abhikpal, 2017-06-14)
    #
    # All of the buffer stuff needs refactoring.
    #
    shape_hash = str(shape.__dict__)

    if shape_hash not in _geometries:
        vertex_buffer = GLuint()
        glGenBuffers(1, pointer(vertex_buffer))

        index_buffer = GLuint()
        glGenBuffers(1, pointer(index_buffer))

        glBindBuffer(GL_ARRAY_BUFFER, vertex_buffer)

        vertices = [vi for vertex in shape.vertices for vi in vertex]
        vertices_typed =  (GLfloat * len(vertices))(*vertices)

        glBufferData(
            GL_ARRAY_BUFFER,
            sizeof(vertices_typed),
            vertices_typed,
            GL_STATIC_DRAW
        )

        elements = [idx for face in shape.faces for idx in face]
        elements_typed = (GLuint * len(elements))(*elements)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, index_buffer)
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            sizeof(elements_typed),
            elements_typed,
            GL_STATIC_DRAW
        )

        position_attr = glGetAttribLocation(_shader_program.pid, b"position")
        glEnableVertexAttribArray(position_attr)
        glVertexAttribPointer(position_attr, 3, GL_FLOAT, GL_FALSE, 0, 0)

        _geometries[shape_hash] = {
            'vertex_buffer': vertex_buffer,
            'index_buffer': index_buffer,
            'num_elements': len(elements)
        }

    _shader_program['model'] = transform_matrix

    glBindBuffer(GL_ARRAY_BUFFER, _geometries[shape_hash]['vertex_buffer'])

    position_attr = glGetAttribLocation(_shader_program.pid, b"position")
    glEnableVertexAttribArray(position_attr)
    glVertexAttribPointer(position_attr, 3, GL_FLOAT, GL_FALSE, 0, 0)

    if fill_enabled and (shape.kind not in ['POINT', 'LINE']):
        _shader_program['fill_color'] =  fill_color

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, _geometries[shape_hash]['index_buffer'])
        glDrawElements(
            GL_TRIANGLES,
            _geometries[shape_hash]['num_elements'],
            GL_UNSIGNED_INT,
            0
        )
    if stroke_enabled:
        _shader_program['fill_color'] = stroke_color
        if shape.kind is 'POINT':
            glDrawElements(
                GL_POINTS,
                _geometries[shape_hash]['num_elements'],
                GL_UNSIGNED_INT,
                0
            )
        else:
            glDrawElements(
                GL_LINE_LOOP,
                _geometries[shape_hash]['num_elements'],
                GL_UNSIGNED_INT,
                0
            )

def test_render():
    """Render the renderer's default test drawing."""
    global background_color
    global fill_color

    class Triangle:
        def __init__(self):
            self.faces = [(0, 1, 2)]
            self.kind = 'POLY'
            self.vertices = [
                (450, 150, 0),
                (600, 450, 0),
                (750, 150, 0)
            ]

    class Square:
        def __init__(self):
            self.faces = [(0, 1, 2), (2, 3, 0)]
            self.kind = 'POLY'
            self.vertices = [
                (50, 150, 0),
                (50, 450, 0),
                (350, 450, 0),
                (350, 150, 0)
            ]

    background_color = (1.0, 1.0, 1.0, 1.0)
    clear()

    fill_color = (0.8, 0.8, 0.4, 1.0)
    render(Triangle())

    fill_color = (0.4, 0.4, 0.8, 1.0)
    render(Square())
