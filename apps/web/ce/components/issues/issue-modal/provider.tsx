/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useMemo, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import type { ISearchIssueResponse, TIssue } from "@plane/types";
// components
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useUser } from "@/hooks/store/user/user-user";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds } = props;
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  const { getProjectDefaultIssueTypeId } = useIssueTypes();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  const contextValue = useMemo(
    () => ({
      allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
      workItemTemplateId: null,
      setWorkItemTemplateId: () => {},
      isApplyingTemplate: false,
      setIsApplyingTemplate: () => {},
      selectedParentIssue,
      setSelectedParentIssue,
      issuePropertyValues: {},
      setIssuePropertyValues: () => {},
      issuePropertyValueErrors: {},
      setIssuePropertyValueErrors: () => {},
      getIssueTypeIdOnProjectChange: (projectId: string) => getProjectDefaultIssueTypeId(projectId) ?? null,
      getActiveAdditionalPropertiesLength: () => 0,
      handlePropertyValuesValidation: () => true,
      handleCreateUpdatePropertyValues: () => Promise.resolve(),
      handleProjectEntitiesFetch: () => Promise.resolve(),
      handleTemplateChange: () => Promise.resolve(),
      handleConvert: () => Promise.resolve(),
      handleCreateSubWorkItem: () => Promise.resolve(),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allowedProjectIds, projectIdsWithCreatePermissions, selectedParentIssue, getProjectDefaultIssueTypeId]
  );

  return <IssueModalContext.Provider value={contextValue}>{children}</IssueModalContext.Provider>;
});
