import type { BugOut, CaseOut, GraphOut, PlanOut, VersionOut } from "../api/types";

export const GV = "gv_" + "1".repeat(32);
export const PLAN = "pln_" + "2".repeat(32);
export const RUN = "run_" + "3".repeat(32);

export const version: VersionOut = { id: GV, number: 1, status: "draft", approved_at: null, nodes: 2, pending: 1 };

export const graph: GraphOut = {
  version,
  nodes: [
    {
      id: "nod_1",
      type: "Rule",
      label: "Password is 8 to 64 characters",
      attrs: {},
      review_status: "pending",
      citations: [
        {
          source_id: "src_1",
          file: "prd.pdf",
          quote: "Passwords must be between 8 and 64 characters.",
          start_offset: 10,
          end_offset: 56,
          page: 3,
          line: 12,
          status: "verified",
        },
      ],
    },
    {
      id: "nod_2",
      type: "Journey",
      label: "Checkout",
      attrs: {},
      review_status: "approved",
      citations: [],
    },
  ],
  edges: [],
};

export const plan: PlanOut = {
  id: PLAN,
  status: "draft",
  graph_version_id: GV,
  cost_estimate: { available: true, model: "claude-opus-5-5", input_tokens: 1000, output_tokens: 500, usd: 1.2, minutes: 3 },
  suggested_total: 6,
  approved_total: 6,
  segments: [
    {
      id: "seg_1",
      journey_id: "nod_2",
      journey: "Checkout",
      rows: [
        { technique: "happy_path", count: 2, reason: "2 roles can check out" },
        { technique: "boundary", count: 4, reason: "quantity limit 1 to 99" },
      ],
      base_count: 6,
      multiplier: 1,
      risk_score: 0.8,
      priority: "Must",
      suggested_count: 6,
      approved_count: null,
      previous_decision: null,
    },
  ],
};

export const verifiedCase: CaseOut = {
  id: "tc_1",
  code: "TC-001",
  segment_id: "seg_1",
  title: "Checkout with one item",
  role: "shopper",
  technique: "happy_path",
  priority: "Must",
  preconditions: ["Cart has one item"],
  data: { qty: "1" },
  expected_text: "Order confirmation is shown",
  citation: { status: "verified", quote: "After payment the order confirmation page is shown.", source_id: "s", start_offset: 0, end_offset: 10 },
  requirement_id: null,
  review_status: "pending",
  steps: [
    { n: 1, action: "Open the cart" },
    { n: 2, action: "Press Pay" },
  ],
};

export const uvCase: CaseOut = {
  ...verifiedCase,
  id: "tc_2",
  code: "TC-002",
  title: "Checkout shows a discount",
  expected_text: "A 10% discount is applied",
  citation: { status: "unable_to_verify", quote: "Members get 10% off.", reason: "quote not found" },
};

export const draftBug: BugOut = {
  id: "bug_1",
  run_id: RUN,
  case_id: "tc_1",
  title: "Pay button does nothing",
  severity: "high",
  body_md: "**Steps**\n1. Press Pay\n<script>alert(1)</script>",
  status: "draft",
  tracker_ref: null,
};
