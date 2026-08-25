// @ts-check
const autoLabeler = require("../../.github/workflows/scripts/auto-labeler");

describe("auto-labeler script", () => {
  let mockGithub;
  let mockContext;

  // Exact short labels from your updated PR template mapping
  const labelFeature = "🚀 feat";
  const labelBugfix = "🐞 fix";
  const labelCi = "🤖 ci";
  const labelBreaking = "🚨 break";
  const labelVerify = "💻 verify";

  beforeEach(() => {
    // 1. Create structured mock objects for Octokit REST API
    mockGithub = {
      rest: {
        issues: {
          listLabelsOnIssue: jest.fn().mockResolvedValue({
            // Mock initial state: PR already has a 'fix' label and one custom user label
            data: [{ name: labelBugfix }, { name: "custom-user-label" }],
          }),
          removeLabel: jest.fn().mockResolvedValue({}),
          addLabels: jest.fn().mockResolvedValue({}),
          listComments: jest.fn().mockResolvedValue({
            // Mock historical warning comments left by older workflow versions
            data: [
              {
                id: 111,
                user: { type: "Bot" },
                body: "Please select at least one Type of Change warning",
              },
              {
                id: 222,
                user: { type: "Bot" },
                body: "automated release notes generation notice",
              },
              {
                id: 333,
                user: { type: "User" },
                body: "Regular developer review comment",
              },
            ],
          }),
          deleteComment: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions context
    mockContext = {
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        pull_request: {
          number: 303,
          title: "Any manual PR title",
          body: `## 🛠️ Type of Change:\n- [ ] **${labelBugfix}**\n- [x] **${labelFeature}**`,
          user: { login: "developer_one" },
        },
      },
    };
  });

  it("should dynamically extract label from asterisks, add it, remove the old unchecked label, and sweep old bot comments", async () => {
    // Execute the simplified script passing only github and context
    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the unchecked semantic label is successfully removed
    expect(mockGithub.rest.issues.removeLabel).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      name: labelBugfix,
    });

    // Verify that custom non-template labels are NOT touched by the script
    expect(mockGithub.rest.issues.removeLabel).not.toHaveBeenCalledWith(
      expect.objectContaining({ name: "custom-user-label" })
    );

    // Verify that the newly checked 'feat' label is correctly added
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelFeature],
    });

    // Verify that both old bot warning comments (ID 111 and 222) were successfully cleaned up
    expect(mockGithub.rest.issues.deleteComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      comment_id: 111,
    });

    expect(mockGithub.rest.issues.deleteComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      comment_id: 222,
    });

    // Verify that regular human developer comments (ID 333) are never touched
    expect(mockGithub.rest.issues.deleteComment).not.toHaveBeenCalledWith(
      expect.objectContaining({ comment_id: 333 })
    );
  });

  it("should successfully parse checkbox with uppercase X", async () => {
    mockContext.payload.pull_request.body = `## 🛠️ Type of Change:\n- [X] **${labelCi}**`;
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelCi],
    });
  });

  it("should parse multiple checked labels including breaking changes and quality checklist items altogether", async () => {
    // Simulated layout matching your final template format completely
    mockContext.payload.pull_request.body = `## 🛠️ Type of Change:\n- [x] **${labelBugfix}**\n\n## 🚨 Breaking Changes\n- [x] **${labelBreaking}** (breaking)\n\n## ✅ Checklist:\n- [x] **${labelVerify}** (locally tested)`;

    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Expect ALL three checked boxes to be pushed as labels seamlessly
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelBugfix],
    });

    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelBreaking],
    });

    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelVerify],
    });
  });
});
