#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright:
#   2020 P. H. <github.com/perfide>
# License:
#   GPL-2.0-only (GNU General Public License v2.0 only)
#   https://spdx.org/licenses/GPL-2.0-only.html

"""Jinja2 template renderer

This script takes Jinja2 templates from one direcory and
YAML-variables files from other directory-structure.
It then renders the templates to a third directory with the same structure as
the variables have.

Example:
    stacks/
      production/
        a/
          example
      staging/
        a/
          example
    templates/
      example.j2
    vars/
      production/
        a/
          main.yaml
          second.yaml
      staging/
        a/
          main.yaml

The values from the variables-directory-structure are being used for the
corrosponding directories in the stacks folder.
"""

# included
import argparse
import os
import sys

# 3rd-party
import jinja2
import yaml


class RendererFailed(Exception):
    """Raised if a Jinja2 operation failed"""


class YamlReadFailed(Exception):
    """A YAML file read failed"""


def render_one_file(
    env: jinja2.environment.Environment,
    template_file_name: str,
    output_dir: str,
    variables: dict,
) -> None:
    """Merge variables for the current output dir and render

    Args:
        env: Jinja2 Environment object
        template_file_name: Jinja2 template file name
        output_dir: Directory for rendered files
        variables: Variables to be used for rendering

    Returns:
        None

    """
    try:
        tmpl = env.get_template(template_file_name)
    except jinja2.exceptions.TemplateSyntaxError as err:
        # expected token 'end of statement block', got '='
        raise RendererFailed(f'Bad template: {err}')
    try:
        rendered = tmpl.render(**variables)
    except jinja2.exceptions.UndefinedError as err:
        # 'dict object' has no attribute 'worker'
        raise RendererFailed(f'Missing variable: {err}')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, template_file_name)
    with open(output_path, 'w') as file_handler:
        file_handler.write(rendered)
        # the jinja renderer seems to strip the end-of-file new-line
        file_handler.write('\n')
    return


def render_one_dir(
    templates_dir: str, output_dir: str, variables: dict
) -> None:
    """Merge variables for the current output dir and render

    Args:
        templates_dir: Directory with Jinja2 templates
        output_dir: Directory for rendered files
        variables: Variables to be used for rendering

    Returns:
        None

    """
    fs_loader = jinja2.FileSystemLoader(templates_dir, encoding='utf-8')

    env = jinja2.Environment(loader=fs_loader)
    # env: jinja2.environment.Environment

    if 'templates' in variables:
        template_file_names = [
            f'{name}.yaml' for name in variables['templates']
        ]
    else:
        template_file_names = env.list_templates()

    for name in variables.get('exclude', set()):
        try:
            template_file_names.remove(f'{name}.yaml')
        except ValueError:
            pass

    for template_file_name in template_file_names:
        if template_file_name.startswith('partials/'):
            continue
        render_one_file(env, template_file_name, output_dir, variables)

    return


def merge_level_variables(level_names: tuple, variables: dict) -> dict:
    """Merge variables for the current output dir and render

    Args:
        level_names: Folder-split
        variables: Folder-split to folder-variables

    Returns:
        Merged variables

    """
    merged_variables = {}
    while True:
        cur_variables = variables[level_names]
        merged_variables = merge_dict(cur_variables, merged_variables)
        if not level_names:
            break
        level_names = level_names[:-1]
    return merged_variables


def handle_variables(
    templates_dir: str, output_dir: str, variables: dict, max_depth: int
) -> None:
    """Merge variables for the current output dir and render

    Args:
        templates_dir: Directory with Jinja2 templates
        output_dir: Directory for rendered files
        variables: Folder-split to folder-variables
        max_depth: Highest variables directory depth found

    Returns:
        None

    """
    for level_names in variables:
        if len(level_names) == max_depth:
            cur_output_dir = os.path.join(output_dir, *level_names)
            cur_variables = merge_level_variables(level_names, variables)
            render_one_dir(templates_dir, cur_output_dir, cur_variables)
    return


def merge_dict(dict1: dict, dict2: dict) -> dict:
    """Recursive dict.update

    Args:
        dict1: Rezessive target which gets overridden
        dict2: Source with most importance

    Returns:
        Merged dict

    """
    dict1 = dict1.copy()
    dict2 = dict2.copy()
    for key, value2 in dict2.items():
        if key in dict1:
            if isinstance(dict1[key], dict) and isinstance(value2, dict):
                dict1[key] = merge_dict(dict1[key], value2)
            elif isinstance(dict1[key], dict) ^ isinstance(value2, dict):
                msg = f'incompatible structure: {dict1[key]} vs. {value2}'
                raise KeyError(msg)
            else:
                dict1[key] = value2
        else:
            dict1[key] = value2
    return dict1


def read_yaml(yaml_path: str) -> dict:
    """Read a YAML file

    Args:
        yaml_path: File-system-path to the YAML-file

    Returns:
        Parsed content

    """
    variables = {}
    with open(yaml_path, 'rt') as file_handler:
        try:
            variables = yaml.safe_load(file_handler.read())
        except yaml.parser.ParserError as err:
            msg = f'unable to parse {yaml_path}: """{err}"""'
            YamlReadFailed(msg)
        except yaml.scanner.ScannerError as err:
            msg = f'unable to scan {yaml_path}: """{err}"""'
            YamlReadFailed(msg)
        except UnicodeDecodeError as err:
            msg = f'unable to decode {yaml_path}: """{err}"""'
            YamlReadFailed(msg)
    return variables


def read_all_variables(base_dir: str) -> tuple:
    """Walk through the variables-dir, read and merge all variables found

    Args:
        variables_dir: Directory with YAML variables
        templates_dir: Directory with Jinja2 templates
        output_dir: Directory for rendered files

    Returns:
        max_depth (int): Highest variables directory depth found
        variables (dict): Folder-split to folder-variables

    """
    max_depth = 0
    variables = {}
    for root, _, files in os.walk(base_dir):
        level_variables = {}
        for cur_file in files:
            cur_path = os.path.join(root, cur_file)
            cur_variables = read_yaml(cur_path)
            if isinstance(cur_variables, dict):
                level_variables = merge_dict(level_variables, cur_variables)
        rel_dir = root[len(base_dir):].lstrip('/')
        if rel_dir:
            level_names = tuple(rel_dir.split(os.sep))
        else:
            level_names = tuple()
        cur_len = len(level_names)
        if cur_len > max_depth:
            max_depth = cur_len
        variables[level_names] = level_variables
    return (max_depth, variables)


def main(variables_dir: str, templates_dir: str, output_dir: str) -> int:
    """Read a YAML file

    Args:
        variables_dir: Directory with YAML variables
        templates_dir: Directory with Jinja2 templates
        output_dir: Directory for rendered files

    Returns:
        Exit code for the script

    """
    variables_dir = os.path.expanduser(variables_dir)
    templates_dir = os.path.expanduser(templates_dir)
    output_dir = os.path.expanduser(output_dir)
    if not os.path.isdir(templates_dir):
        print(f'Templates not found in "{templates_dir}"')
        return 3
    if not os.path.isdir(variables_dir):
        print(f'Variables not found in "{variables_dir}"')
        return 2
    (max_depth, variables) = read_all_variables(variables_dir)
    try:
        handle_variables(templates_dir, output_dir, variables, max_depth)
    except RendererFailed as err:
        print(f'Failed to render: {err}')
        return 1
    return 0


def parse_args(args: list) -> argparse.Namespace:
    """Parse command-line arguments

    Args:
        args: Command-line arguments without the programm-name

    Returns:
        Parsed arguments

    """
    parser = argparse.ArgumentParser(
        description='Use a yaml-variables to render Jinja2 templates'
    )
    parser.add_argument(
        '-b',
        '--base',
        help='Base directory',
    )
    parser.add_argument(
        '-o',
        '--output',
        default='output',
        help='Output directory',
    )
    parser.add_argument(
        '-p',
        '--templates',
        default='templates',
        help='Templates directory',
    )
    parser.add_argument(
        '-v',
        '--variables',
        default='vars',
        help='Variables directory',
    )
    return parser.parse_args(args)


if __name__ == '__main__':
    NAMESPACE = parse_args(sys.argv[1:])
    EXIT_CODE = main(
        NAMESPACE.variables, NAMESPACE.templates, NAMESPACE.output
    )
    sys.exit(EXIT_CODE)

# [EOF]
