// @ts-check
const autoLabeler = require("../../.github/workflows/scripts/auto-labeler");

describe("auto-labeler script", () => {
  let mockGithub;
  let mockContext;
  let mockCore;

  // Exact Unicode constants to match the script's short naming convention perfectly
  const labelFeature = "\uD83D\uDE80 feat";
  const labelBugfix = "\uD83D\uDC1E fix";
  const labelCi = "\uD83E\uDD16 ci";
  const labelBreaking = "\uD83D\uDEA8 break";

  beforeEach(() => {
    // 1. Create deeply structured mock objects for Octokit REST API methods
    mockGithub = {
      rest: {
        issues: {
          listLabelsOnIssue: jest.fn().mockResolvedValue({
            // Mock initial labels on PR with the new short name format
            data: [{ name: labelBugfix }, { name: "custom-user-label" }],
          }),
          removeLabel: jest.fn().mockResolvedValue({}),
          addLabels: jest.fn().mockResolvedValue({}),
          listComments: jest.fn().mockResolvedValue({
            data: [
              {
                id: 111,
                user: { type: "Bot" },
                body: "automated release notes generation warning",
              },
              { id: 222, user: { type: "User" }, body: "Regular developer comment" },
            ],
          }),
          deleteComment: jest.fn().mockResolvedValue({}),
          createComment: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        pull_request: {
          number: 303,
          title: "Any manual title text",
          body: "## \uD83D\uDEE0\uFE0F Type of Change\n- [ ] **Security Update**\n- [x] **New Feature**\n- [ ] **Bug Fix**",
          user: { login: "developer_one" },
        },
      },
    };

    // 3. Create a mock object for the GitHub Actions core library
    mockCore = {
      setFailed: jest.fn(),
    };
  });

  it("should add a new label from checkbox, remove the old semantic label, and delete the bot comment", async () => {
    // Execute the script where 'New Feature' is checked, and short 'fix' already exists on PR
    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the old short semantic label is successfully removed
    expect(mockGithub.rest.issues.removeLabel).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      name: labelBugfix,
    });

    // Verify that custom non-semantic labels like 'custom-user-label' are NOT touched
    expect(mockGithub.rest.issues.removeLabel).not.toHaveBeenCalledWith(
      expect.objectContaining({ name: "custom-user-label" })
    );

    // Verify that the new feature label was correctly applied based on the checkbox
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelFeature],
    });

    // Verify that the old validation warning comment left by the bot was deleted
    expect(mockGithub.rest.issues.deleteComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      comment_id: 111,
    });

    // Verify that the step did NOT fail
    expect(mockCore.setFailed).not.toHaveBeenCalled();
  });

  it("should successfully parse checkbox with uppercase X", async () => {
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [X] **CI/CD & Tooling**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelCi],
    });
  });

  it("should create a warning comment and fail the step if no checkboxes are selected", async () => {
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [ ] **Bug Fix**\n- [ ] **New Feature**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });
    mockGithub.rest.issues.listComments.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith(
      expect.objectContaining({
        owner: "gigaflux",
        repo: "gflx-clickhouse-macro",
        issue_number: 303,
        body: expect.stringContaining("categorize this change"),
      })
    );

    expect(mockCore.setFailed).toHaveBeenCalledWith(
      "Validation failed: No 'Type of Change' was selected in the PR description."
    );

    // Verify that no labels were added since it returned early
    expect(mockGithub.rest.issues.addLabels).not.toHaveBeenCalled();
  });

  it("should add a breaking-change label when Breaking Changes section is checked", async () => {
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [x] **Bug Fix**\n\n## Breaking Changes\n- [x] This PR introduces a breaking change";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify labels are applied separately (including the new short breaking label)
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
  });
});
