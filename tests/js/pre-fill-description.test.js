// @ts-check
const preFillDescription = require("../../.github/workflows/scripts/pre-fill-description");

describe("pre-fill-description script", () => {
  let mockGithub;
  let mockContext;

  beforeEach(() => {
    // 1. Create deeply structured mock objects for the Octokit REST API methods
    delete process.env.ACT;
    mockGithub = {
      rest: {
        pulls: {
          listCommits: jest.fn().mockResolvedValue({
            data: [
              {
                commit: { message: "feat: add clickhouse macro\n\nDetailed breakdown here" },
                author: { login: "test" },
              },
              {
                // Simulate a local commit with no associated GitHub profile (author returns null)
                commit: {
                  message: "fix: escape macro queries",
                  author: { name: "local" },
                },
                author: null,
              },
            ],
          }),
          get: jest.fn().mockResolvedValue({
            data: { body: "## Description\nInitial PR description text goes here." },
          }),
          update: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      issue: { number: 101 },
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        pull_request: {
          body: "## Description\nInitial PR description text goes here.",
        },
        mock_commits: [
          {
            commit: { message: "feat: add clickhouse macro\n\nDetailed breakdown here" },
            author: { login: "test" },
          },
          {
            commit: {
              message: "fix: escape macro queries",
              author: { name: "local" },
            },
            author: null,
          },
        ],
      },
    };
  });

  it("should fetch commits, format them, and inject history into ## Description section", async () => {
    // Execute the script under test
    await preFillDescription(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the commit list was requested for the correct repository and PR number
    expect(mockGithub.rest.pulls.listCommits).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 101,
    });

    const expectedHistory =
      "* feat: add clickhouse macro (by @test)\n" + "* fix: escape macro queries (by @local)";

    // Verify that the PR update method was triggered with the properly injected Markdown history
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 101,
      body: `## Description\n<!-- Automatically gathered commit history. Feel free to adapt or rewrite: -->\n### Commit History:\n${expectedHistory}\n\nInitial PR description text goes here.`,
    });
  });

  it("should update the PR body unmodified if ## Description section is missing", async () => {
    // Stub out the initial PR text to a body without the standard target header
    mockGithub.rest.pulls.get.mockResolvedValue({
      data: { body: "Just some text without required standard section header." },
    });

    await preFillDescription(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // The script should handle this gracefully without crashing and keep the body intact
    expect(mockGithub.rest.pulls.update).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      pull_number: 101,
      body: "Just some text without required standard section header.",
    });
  });
});
