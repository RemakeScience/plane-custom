/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import { observer } from "mobx-react";
// plane imports
import { CloseIcon } from "@plane/propel/icons";
import { Logo } from "@plane/propel/emoji-icon-picker";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";

type Props = {
  handleRemove: (val: string) => void;
  values: string[];
  editable: boolean | undefined;
};

export const AppliedIssueTypeFilters = observer(function AppliedIssueTypeFilters(props: Props) {
  const { handleRemove, values, editable } = props;
  // store
  const { getIssueTypeById } = useIssueTypes();

  return (
    <>
      {values.map((issueTypeId) => {
        const issueType = getIssueTypeById(issueTypeId);
        if (!issueType) return null;

        return (
          <div key={issueTypeId} className="flex items-center gap-1 rounded-sm bg-layer-1 p-1 text-11">
            {issueType.logo_props?.in_use && <Logo logo={issueType.logo_props} size={12} />}
            <span className="normal-case">{issueType.name}</span>
            {editable && (
              <button
                type="button"
                className="grid place-items-center text-tertiary hover:text-secondary"
                onClick={() => handleRemove(issueTypeId)}
              >
                <CloseIcon height={10} width={10} strokeWidth={2} />
              </button>
            )}
          </div>
        );
      })}
    </>
  );
});
