/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import React from "react";
import { observer } from "mobx-react";
import { EIssuesStoreType } from "@plane/types";
import type { TIssue } from "@plane/types";
// components
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";

export interface EpicModalProps {
  data?: Partial<TIssue>;
  isOpen: boolean;
  onClose: () => void;
  beforeFormSubmit?: () => Promise<void>;
  onSubmit?: (res: TIssue) => Promise<void>;
  fetchIssueDetails?: boolean;
  primaryButtonText?: {
    default: string;
    loading: string;
  };
  isProjectSelectionDisabled?: boolean;
}

/**
 * Create / update modal for epics. Reuses the work item modal but scopes it to
 * the EPIC store (`isEpicModal`) so submission hits the `/epics/` API, which
 * forces the project epic type server-side.
 */
export const CreateUpdateEpicModal = observer(function CreateUpdateEpicModal(props: EpicModalProps) {
  return (
    <CreateUpdateIssueModal
      data={props.data}
      isOpen={props.isOpen}
      onClose={props.onClose}
      beforeFormSubmit={props.beforeFormSubmit}
      onSubmit={props.onSubmit}
      fetchIssueDetails={props.fetchIssueDetails}
      primaryButtonText={props.primaryButtonText}
      isProjectSelectionDisabled={props.isProjectSelectionDisabled}
      storeType={EIssuesStoreType.EPIC}
      isEpicModal
      withDraftIssueWrapper={false}
    />
  );
});
