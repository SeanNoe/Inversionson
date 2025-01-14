from __future__ import annotations

from inversionson.project import Project


class Component(object):
    """
    Base class for components that are added to Project
    """

    def __init__(self, project: Project):
        assert isinstance(project, Project)
        self.project = project
