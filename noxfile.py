# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2021, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import pathlib
import shutil

import nox

nox.options.sessions = ["reformat", "lint", "spell-check", "type-check", "test"]  # type: ignore
GENERAL_TARGETS = ["./examples", "./noxfile.py", "./tanjun", "./tests"]
PYTHON_VERSIONS = ["3.9", "3.10"]  # TODO: @nox.session(python=["3.6", "3.7", "3.8"])?
REQUIREMENTS = [
    # Temporarily assume #master for hikari and yuyo
    "git+https://github.com/FasterSpeeding/hikari.git@task/api-impl-export",
    "git+https://github.com/FasterSpeeding/Yuyo.git@task/cache-and-list",
    ".",
]


def install_requirements(
    session: nox.Session, *other_requirements: str, include_standard_requirements: bool = True
) -> None:
    session.install("--upgrade", "wheel")
    requirements = [*REQUIREMENTS, *other_requirements]

    if include_standard_requirements:
        pass

    session.install("--upgrade", *requirements)


@nox.session(venv_backend="none")
def cleanup(session: nox.Session) -> None:
    # Remove directories
    from nox.logger import logger

    for raw_path in ["./dist", "./docs", "./.nox", "./.pytest_cache", "./hikari_tanjun.egg-info"]:
        path = pathlib.Path(raw_path)
        try:
            shutil.rmtree(str(path.absolute()))

        except Exception as exc:
            logger.error(f"[ FAIL ] Failed to remove '{raw_path}': {exc!s}")  # type: ignore

        else:
            logger.info(f"[  OK  ] Removed '{raw_path}'")  # type: ignore

    # Remove individual files
    for raw_path in ["./.coverage"]:
        path = pathlib.Path(raw_path)
        try:
            path.unlink()

        except Exception as exc:
            logger.error(f"[ FAIL ] Failed to remove '{raw_path}': {exc!s}")  # type: ignore

        else:
            logger.info(f"[  OK  ] Removed '{raw_path}'")  # type: ignore


@nox.session(name="generate-docs", reuse_venv=True)
def generate_docs(session: nox.Session) -> None:
    install_requirements(session, ".[docs]")
    session.log("Building docs into ./docs")
    session.run("pdoc", "--docformat", "numpy", "-o", "./docs", "./tanjun")
    session.log("Docs generated: %s", pathlib.Path("./docs/index.html").absolute())


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    install_requirements(session, ".[flake8]")
    session.run("flake8", *GENERAL_TARGETS)


@nox.session(reuse_venv=True, name="spell-check")
def spell_check(session: nox.Session) -> None:
    install_requirements(session, ".[lint]", include_standard_requirements=False)
    session.run("codespell", *GENERAL_TARGETS, ".flake8", ".gitignore", "LICENSE", "pyproject.toml", "README.md")


@nox.session(reuse_venv=True)
def build(session: nox.Session) -> None:
    session.install("flit")
    session.log("Starting build")
    session.run("flit", "build")


@nox.session(reuse_venv=True)
def publish(session: nox.Session, test: bool = False) -> None:
    if not session.interactive:
        session.log("PYPI upload unavailable in non-interactive session")
        return

    session.install("flit")
    if test:
        session.log("Initiating TestPYPI upload")
        session.run("flit", "publish", "--repository", "testpypi")

    else:
        session.log("Initiating PYPI upload")
        session.run("flit", "publish")


@nox.session(name="test-publish", reuse_venv=True)
def test_publish(session: nox.Session) -> None:
    publish(session, test=True)


@nox.session(reuse_venv=True)
def reformat(session: nox.Session) -> None:
    install_requirements(session, ".[reformat]", include_standard_requirements=False)
    session.run("black", *GENERAL_TARGETS)
    session.run("isort", *GENERAL_TARGETS)


@nox.session(reuse_venv=True)
def test(session: nox.Session) -> None:
    install_requirements(session, ".[tests]")
    # TODO: can import-mode be specified in the config.
    session.run("pytest", "--import-mode", "importlib")


@nox.session(name="test-coverage", reuse_venv=True)
def test_coverage(session: nox.Session) -> None:
    install_requirements(session, ".[tests]")
    # TODO: can import-mode be specified in the config.
    session.run("pytest", "--cov=tanjun", "--import-mode", "importlib")


@nox.session(name="type-check", reuse_venv=True)
def type_check(session: nox.Session) -> None:
    install_requirements(session, ".[dev]", ".[tests]")
    session.run("pyright", external=True)