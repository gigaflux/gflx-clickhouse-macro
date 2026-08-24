// @ts-check
const invalidTitleComment = require("../../.github/workflows/scripts/invalid-title-comment");

describe("invalid-title-comment script", () => {
  let mockGithub;
  let mockContext;

  beforeEach(() => {
    // 1. Create structured mock objects for Octokit REST API
    mockGithub = {
      rest: {
        issues: {
          createComment: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      issue: { number: 404 },
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        // Simulate a webhook payload from a PR opened by a specific user
        pull_request: {
          user: {
            login: "contrib-developer",
          },
        },
      },
    };
  });

  it("should generate a validation message and post a comment mentioning the PR author", async () => {
    // Execute the script under test
    await invalidTitleComment(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that createComment was called for the correct repository and issue number
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 404,
      // Check that the body is a string and contains the correct mention tag of the author
      body: expect.stringContaining("👋 Hi @contrib-developer!"),
    });

    // Verify that the comment mentions Conventional Commits guidelines
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 404,
      body: expect.stringContaining("Conventional Commits standard"),
    });
  });

  it("should log a message and exit early if no pull_request payload is present", async () => {
    // Simulate a workflow execution context without a pull request trigger
    mockContext.payload = {};
    const originalLog = console.log;
    console.log = jest.fn();

    await invalidTitleComment(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the script terminates without calling the GitHub API
    expect(mockGithub.rest.issues.createComment).not.toHaveBeenCalled();
    expect(console.log).toHaveBeenCalledWith("No pull request found in context.");

    console.log = originalLog;
  });
});
