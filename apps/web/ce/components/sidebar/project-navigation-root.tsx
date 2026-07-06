/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions } from "@plane/constants";
import { LayersIcon } from "@plane/propel/icons";
// components
import type { TNavigationItem } from "@/components/workspace/sidebar/project-navigation";
import { ProjectNavigation } from "@/components/workspace/sidebar/project-navigation";
// hooks
import { useProject } from "@/hooks/store/use-project";

type TProjectItemsRootProps = {
  workspaceSlug: string;
  projectId: string;
};

export const ProjectNavigationRoot = observer(function ProjectNavigationRoot(props: TProjectItemsRootProps) {
  const { workspaceSlug, projectId } = props;
  // store hooks
  const { getProjectById } = useProject();
  // derived values
  const project = getProjectById(projectId);

  // Inject the Epics tab (gated by the project's is_epic_enabled flag), sorted
  // right after Work items.
  const additionalNavigationItems = (currentWorkspaceSlug: string, currentProjectId: string): TNavigationItem[] => [
    {
      i18n_key: "sidebar.epics",
      key: "epics",
      name: "Epics",
      href: `/${currentWorkspaceSlug}/projects/${currentProjectId}/epics`,
      icon: LayersIcon,
      access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER, EUserPermissions.GUEST],
      shouldRender: project?.is_epic_enabled ?? false,
      sortOrder: 1.5,
    },
  ];

  return (
    <ProjectNavigation
      workspaceSlug={workspaceSlug}
      projectId={projectId}
      additionalNavigationItems={additionalNavigationItems}
    />
  );
});
