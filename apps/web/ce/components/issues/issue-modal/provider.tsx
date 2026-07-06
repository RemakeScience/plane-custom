/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import type { ISearchIssueResponse, TIssue, TIssuePropertyValues, TIssuePropertyValueErrors } from "@plane/types";
// components
import type {
  TActiveAdditionalPropertiesProps,
  TCreateUpdatePropertyValuesProps,
  THandleProjectEntitiesFetchProps,
  TPropertyValuesValidationProps,
} from "@/components/issues/issue-modal/context";
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useIssueProperties } from "@/hooks/store/use-issue-properties";
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useUser } from "@/hooks/store/user/user-user";
// services
import { IssuePropertyValueService } from "@/services/issue-property-value.service";

const issuePropertyValueService = new IssuePropertyValueService();

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
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>({});
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  // keep a ref of the latest values so the imperative handlers never read stale state
  const issuePropertyValuesRef = useRef<TIssuePropertyValues>(issuePropertyValues);
  issuePropertyValuesRef.current = issuePropertyValues;
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  const { getProjectDefaultIssueTypeId } = useIssueTypes();
  const { fetchProjectProperties, getTypeProperties } = useIssueProperties();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  const getActiveAdditionalPropertiesLength = useCallback(
    ({ projectId, watch }: TActiveAdditionalPropertiesProps) => {
      const typeId = watch("type_id");
      if (!projectId || !typeId) return 0;
      return getTypeProperties(projectId, typeId, true)?.length ?? 0;
    },
    [getTypeProperties]
  );

  const handlePropertyValuesValidation = useCallback(
    ({ projectId, watch }: TPropertyValuesValidationProps) => {
      const typeId = watch("type_id");
      if (!projectId || !typeId) return true;
      const properties = getTypeProperties(projectId, typeId, true) ?? [];
      const errors: TIssuePropertyValueErrors = {};
      properties.forEach((property) => {
        if (!property.is_required) return;
        const values = (issuePropertyValuesRef.current[property.id] ?? []).filter(
          (value) => value !== null && value !== "" && value !== undefined
        );
        if (values.length === 0) errors[property.id] = `${property.display_name} is required`;
      });
      setIssuePropertyValueErrors(errors);
      return Object.keys(errors).length === 0;
    },
    [getTypeProperties]
  );

  const handleCreateUpdatePropertyValues = useCallback(
    async ({ issueId, projectId, workspaceSlug, issueTypeId }: TCreateUpdatePropertyValuesProps) => {
      const currentValues = issuePropertyValuesRef.current;
      // When the type is known, only send the values of that type's properties;
      // otherwise (the create response may omit type_id) send everything the
      // user entered — the backend scopes properties to the project anyway.
      let payload: TIssuePropertyValues = currentValues;
      if (issueTypeId) {
        const properties = getTypeProperties(projectId, issueTypeId, true) ?? [];
        payload = {};
        properties.forEach((property) => {
          payload[property.id] = currentValues[property.id] ?? [];
        });
      }
      if (Object.keys(payload).length === 0) return;
      await issuePropertyValueService.upsert(workspaceSlug, projectId, issueId, payload);
    },
    [getTypeProperties]
  );

  const handleProjectEntitiesFetch = useCallback(
    async ({ workItemProjectId, workspaceSlug }: THandleProjectEntitiesFetchProps) => {
      if (!workItemProjectId) return;
      await fetchProjectProperties(workspaceSlug, workItemProjectId);
    },
    [fetchProjectProperties]
  );

  const contextValue = useMemo(
    () => ({
      allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
      workItemTemplateId: null,
      setWorkItemTemplateId: () => {},
      isApplyingTemplate: false,
      setIsApplyingTemplate: () => {},
      selectedParentIssue,
      setSelectedParentIssue,
      issuePropertyValues,
      setIssuePropertyValues,
      issuePropertyValueErrors,
      setIssuePropertyValueErrors,
      getIssueTypeIdOnProjectChange: (projectId: string) => getProjectDefaultIssueTypeId(projectId) ?? null,
      getActiveAdditionalPropertiesLength,
      handlePropertyValuesValidation,
      handleCreateUpdatePropertyValues,
      handleProjectEntitiesFetch,
      handleTemplateChange: () => Promise.resolve(),
      handleConvert: () => Promise.resolve(),
      handleCreateSubWorkItem: () => Promise.resolve(),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      allowedProjectIds,
      projectIdsWithCreatePermissions,
      selectedParentIssue,
      issuePropertyValues,
      issuePropertyValueErrors,
      getProjectDefaultIssueTypeId,
      getActiveAdditionalPropertiesLength,
      handlePropertyValuesValidation,
      handleCreateUpdatePropertyValues,
      handleProjectEntitiesFetch,
    ]
  );

  return <IssueModalContext.Provider value={contextValue}>{children}</IssueModalContext.Provider>;
});
