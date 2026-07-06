/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { WorkItemTypesSettingsRoot } from "@/components/work-item-types";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { WorkItemTypesProjectSettingsHeader } from "./header";

function WorkItemTypesSettingsPage() {
  // store hooks
  const { currentProjectDetails } = useProject();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();

  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails?.name} - Work Item Types` : undefined;

  // derived values
  const canManage = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);

  if (workspaceUserInfo && !canManage) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<WorkItemTypesProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <WorkItemTypesSettingsRoot />
    </SettingsContentWrapper>
  );
}

export default observer(WorkItemTypesSettingsPage);
