// @ts-check
const invalidTitleComment = require("../../.github/workflows/scripts/invalid-title-comment");

describe("invalid-title-comment script", () => {
  let mockGithub;
  let mockContext;

  beforeEach(() => {
    // 1. Create mock objects for the Octokit REST API
    mockGithub = {
      rest: {
        issues: {
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
          user: { login: "contributor_jack" },
        },
      },
    };
  });

  it("should successfully post an ultra-minimal formatting guide comment", async () => {
    // Execute the script under test
    await invalidTitleComment(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the comment was posted to the correct repository and PR number
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 303,
      body: expect.stringContaining("Hi @contributor_jack!"),
    });

    // Verify that the comment body contains key technical mentions from your new text
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.stringContaining("Conventional Commits standard"),
      })
    );

    // Verify that the breaking change hint is present
    expect(mockGithub.rest.issues.createComment).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.stringContaining("Breaking Change"),
      })
    );
  });
});
