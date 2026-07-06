/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "../common";

/**
 * A Work Item Type (a.k.a. issue type). Workspace-scoped, associated to projects
 * through {@link TProjectIssueType}. When `is_epic` is true the type represents an Epic.
 */
export type TIssueType = {
  id: string;
  name: string;
  description: string;
  logo_props: TLogoProps | undefined;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  level: number;
  workspace: string;
  external_source: string | null;
  external_id: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
};

/**
 * The association between a {@link TIssueType} and a project.
 */
export type TProjectIssueType = {
  id: string;
  issue_type: string;
  project_id: string;
  workspace_id: string;
  level: number;
  is_default: boolean;
};
