// @ts-check
const autoLabeler = require("../../.github/workflows/scripts/auto-labeler");

describe("auto-labeler script", () => {
  let mockGithub;
  let mockContext;

  beforeEach(() => {
    // 1. Create deeply structured mock objects for Octokit REST API methods
    mockGithub = {
      rest: {
        issues: {
          listLabelsOnIssue: jest.fn().mockResolvedValue({
            data: [{ name: "🐞 bugfix" }, { name: "custom-user-label" }],
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
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      issue: { number: 303 },
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        pull_request: { title: "feat(auth): add login page integration" },
      },
    };
  });

  it("should add a new label, remove the old semantic label, and delete the bot comment", async () => {
    // Execute the script with a 'feat' title while a 'bugfix' label already exists
    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the old semantic label '🐞 bugfix' was successfully removed
    expect(mockGithub.rest.issues.removeLabel).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      name: "🐞 bugfix",
    });

    // Verify that custom non-semantic labels like 'custom-user-label' are NOT touched
    expect(mockGithub.rest.issues.removeLabel).not.toHaveBeenCalledWith(
      expect.objectContaining({ name: "custom-user-label" })
    );

    // Verify that the new '🚀 feature' label was correctly applied
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: ["🚀 feature"],
    });

    // Verify that the old validation warning comment left by the bot was deleted
    expect(mockGithub.rest.issues.deleteComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      comment_id: 111,
    });
  });

  it("should successfully parse dependabot titles with automatic group scope", async () => {
    // Simulate a grouped Dependabot PR title with its custom scope brackets
    mockContext.payload.pull_request.title = "chore(npm-version-group): bump eslint from 8 to 9";
    mockGithub.rest.issues.listLabelsOnIssue.mockResolvedValue({ data: [] });

    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the script bypasses the scope and correctly extracts the '⚙️ chore' label
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      labels: ["⚙️ chore"],
    });
  });

  it("should log a message and do nothing if the PR title cannot be parsed", async () => {
    // Set an invalid PR title that does not follow Conventional Commits
    mockContext.payload.pull_request.title = "fixed some random bugs without prefix";

    // 1. Save the original console.log reference
    const originalLog = console.log;

    // 2. Mock console.log manually with a standard Jest mock function
    console.log = jest.fn();

    await autoLabeler(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that no labels were added or removed
    expect(mockGithub.rest.issues.addLabels).not.toHaveBeenCalled();
    expect(mockGithub.rest.issues.removeLabel).not.toHaveBeenCalled();

    // 3. Verify that our manual mock recorded the correct log message
    expect(console.log).toHaveBeenCalledWith("Could not parse PR type from title.");

    // 4. Restore the original console.log function to avoid messing up other logs
    console.log = originalLog;
  });
});
