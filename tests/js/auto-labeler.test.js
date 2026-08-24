// @ts-check
const autoLabeler = require("../../.github/workflows/scripts/auto-labeler");

describe("auto-labeler script", () => {
  let mockGithub;
  let mockContext;
  let mockCore;

  // Exact Unicode constants to match the script mappings perfectly
  const labelFeature = "\uD83D\uDE80 feature";
  const labelBugfix = "\uD83D\uDC1E bugfix";
  const labelCi = "\uD83E\uDD16 ci";
  const labelBreaking = "\uD83D\uDEA8 break";

  beforeEach(() => {
    // 1. Create deeply structured mock objects for Octokit REST API methods
    mockGithub = {
      rest: {
        issues: {
          listLabelsOnIssue: jest.fn().mockResolvedValue({
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
        pulls: {
          update: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        pull_request: {
          number: 303,
          title: "old: original title text",
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
    // Execute the script where 'New Feature' is checked, and 'bugfix' already exists on PR
    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the old semantic label was successfully removed
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
    // Simulate a user checking the checkbox with an uppercase 'X'
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [X] **CI/CD & Tooling**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the script extracts the 'ci' label correctly
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: [labelCi],
    });
  });

  it("should create a warning comment and fail the step if no checkboxes are selected", async () => {
    // Set PR body with no checked options
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [ ] **Bug Fix**\n- [ ] **New Feature**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });
    mockGithub.rest.issues.listComments.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the bot left a warning comment with full repository context
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith(
      expect.objectContaining({
        owner: "gigaflux",
        repo: "gflx-clickhouse-macro",
        issue_number: 303,
        body: expect.stringContaining("categorize this change"), // Проверяем чистый кусок текста без Markdown-разметки
      })
    );

    // Verify that the step was explicitly failed to block the merge
    expect(mockCore.setFailed).toHaveBeenCalledWith(
      "Validation failed: No 'Type of Change' was selected in the PR description."
    );

    // Verify that no labels were added or titles updated since it returned early
    expect(mockGithub.rest.issues.addLabels).not.toHaveBeenCalled();
    expect(mockGithub.rest.pulls.update).not.toHaveBeenCalled();
  });

  it("should update only the type in the title while preserving scope", async () => {
    // Scenario: User changes checkbox to 'Bug Fix' but the title has a custom scope
    mockContext.payload.pull_request.title = "feat(clickhouse): migrate layout structure";
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [x] **Bug Fix**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the title was updated to 'fix', but '(clickhouse)' was preserved perfectly
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 303,
      title: "fix(clickhouse): migrate layout structure",
    });
  });

  it("should prepend the new type if the original PR title does not have any conventional prefix", async () => {
    // Scenario: User did not follow conventional commits in the title at all
    mockContext.payload.pull_request.title = "add missing clickhouse analytical dashboard macro";
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [x] **New Feature**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that the script cleanly prepends the resolved type prefix to the raw text
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 303,
      title: "feat: add missing clickhouse analytical dashboard macro",
    });
  });

  it("should select the highest priority type to build the title when multiple checkboxes are selected", async () => {
    // Scenario: User checked both 'New Feature' (weight 9) and 'Bug Fix' (weight 11)
    mockContext.payload.pull_request.title = "chore(core): initial title text";
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [x] **New Feature**\n- [x] **Bug Fix**";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify that 'fix' won the priority race over 'feat', keeping the original scope
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 303,
      title: "fix(core): initial title text",
    });
  });

  it("should add a breaking-change label and inject '!' into the title when Breaking Changes is set to Yes", async () => {
    // Scenario: User selects 'Bug Fix' and checks 'Yes' under Breaking Changes section
    mockContext.payload.pull_request.title = "fix(api): internal query routing";
    mockContext.payload.pull_request.body =
      "## \uD83D\uDEE0\uFE0F Type of Change\n- [x] **Bug Fix**\n\n## \uD83D\uDEA8 Breaking Changes\n- [x] Yes\n- [ ] No";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(
      /** @type {any} */ ({ github: mockGithub, context: mockContext, core: mockCore })
    );

    // Verify labels are applied separately (including the new breaking-change label)
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

    // Verify title sync pushes the breaking '!' right after the scope
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 303,
      title: "fix(api)!: internal query routing",
    });
  });
});
