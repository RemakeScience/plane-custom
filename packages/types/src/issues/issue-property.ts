/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "../common";

/** Supported custom property value types (mirror of the backend enum). */
export enum EIssuePropertyType {
  TEXT = "TEXT",
  DECIMAL = "DECIMAL",
  OPTION = "OPTION",
  BOOLEAN = "BOOLEAN",
  DATETIME = "DATETIME",
  RELATION = "RELATION",
  URL = "URL",
  EMAIL = "EMAIL",
  FILE = "FILE",
}

/** Target of a RELATION property. */
export enum EIssuePropertyRelationType {
  ISSUE = "ISSUE",
  MEMBER = "MEMBER",
}

export type TIssuePropertySettings = Record<string, unknown>;

/**
 * A custom property definition attached to a work item type.
 */
export type TIssueProperty = {
  id: string;
  issue_type: string;
  name: string;
  display_name: string;
  description: string;
  logo_props: TLogoProps | undefined;
  property_type: EIssuePropertyType;
  relation_type: EIssuePropertyRelationType | null;
  is_required: boolean;
  is_multi: boolean;
  is_active: boolean;
  default_value: string[];
  settings: TIssuePropertySettings;
  sort_order: number;
  external_source: string | null;
  external_id: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
};

/**
 * A selectable option for an OPTION-typed property.
 */
export type TIssuePropertyOption = {
  id: string;
  property: string;
  name: string;
  description: string;
  logo_props: TLogoProps | undefined;
  is_active: boolean;
  is_default: boolean;
  sort_order: number;
  parent: string | null;
  external_source: string | null;
  external_id: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
};

/**
 * A property with its options embedded, as returned by the aggregated
 * `issue-property-types/` endpoint.
 */
export type TIssuePropertyWithOptions = TIssueProperty & {
  options: TIssuePropertyOption[];
};
