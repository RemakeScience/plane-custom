/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssueType } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  data: TIssueType | null;
};

export const DeleteIssueTypeModal = observer(function DeleteIssueTypeModal(props: Props) {
  const { isOpen, onClose, workspaceSlug, projectId, data } = props;
  // store hooks
  const { deleteType } = useIssueTypes();
  // states
  const [isDeleting, setIsDeleting] = useState(false);

  const handleClose = () => {
    onClose();
    setIsDeleting(false);
  };

  const handleDeletion = async () => {
    if (!data) return;
    setIsDeleting(true);
    try {
      await deleteType(workspaceSlug, projectId, data.id);
      handleClose();
    } catch (err) {
      setIsDeleting(false);
      const message = (err as { error?: string })?.error ?? "Work item type could not be deleted. Please try again.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message });
    }
  };

  return (
    <AlertModalCore
      handleClose={handleClose}
      handleSubmit={handleDeletion}
      isSubmitting={isDeleting}
      isOpen={isOpen}
      title="Delete work item type"
      content={
        <>
          Are you sure you want to delete <span className="font-medium text-primary">{data?.name}</span>? Work items of
          this type will keep their data but become untyped.
        </>
      }
    />
  );
});
