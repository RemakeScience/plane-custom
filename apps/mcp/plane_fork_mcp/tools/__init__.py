"""Tool modules, registered in this order (the order clients list them)."""

from plane_fork_mcp.tools import catalog, delete, discussion, planning, project, types, workitem

MODULES = (project, workitem, catalog, types, discussion, planning, delete)
