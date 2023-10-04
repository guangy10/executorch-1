# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Sphinx extension to replace ${executorch_version:TAG} with version numbers.

This custom extension pulls third-party version strings from files in the
.ci/docker/ci_commit_pins directory, and uses them to expand specific strings in
markdown files.

For example, `${executorch_version:pytorch}` will be replaced with the
appropriate pytorch version string used by CI.
"""

import os

from docutils import nodes

version_file_names = [
    "buck2.txt",
    "nightly.txt",
    "pytorch.txt",
    "audio.txt",
    "vision.txt",
]

variables = {}


def read_version_files():
    cwd = os.getcwd()
    version_file_path = os.path.join(cwd, "..", ".ci", "docker", "ci_commit_pins")

    for file_name in version_file_names:
        file_path = os.path.join(version_file_path, file_name)
        with open(file_path, "r") as f:
            var_name = "${executorch_version:" + file_name.split(".")[0] + "}"
            variables[var_name] = f.read().strip()


read_version_files()


def replace_variables(app, doctree, docname):
    # Replace in regular text:
    for node in doctree.traverse(nodes.Text):
        new_text = node.astext()
        for var, value in variables.items():
            new_text = new_text.replace(var, value)
        node.parent.replace(node, nodes.Text(new_text))
    # Replace in code blocks:
    for node in doctree.traverse(nodes.literal_block):
        new_text = node.astext()
        for var, value in variables.items():
            new_text = new_text.replace(var, value)
        node.parent.replace(node, nodes.literal_block(new_text, new_text))


def setup(app):
    app.connect("doctree-resolved", replace_variables)