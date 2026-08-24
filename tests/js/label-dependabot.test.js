// @ts-check
const labelDependabot = require("../../.github/workflows/scripts/label-dependabot");

describe("label-dependabot script", () => {
  let mockGithub;
  let mockContext;

  beforeEach(() => {
    // 1. Create deeply structured mock objects for Octokit REST API methods
    mockGithub = {
      rest: {
        issues: {
          addLabels: jest.fn().mockResolvedValue({}),
        },
      },
    };

    // 2. Create a mock object for the GitHub Actions execution context
    mockContext = {
      issue: { number: 202 },
      repo: { owner: "gigaflux", repo: "gflx-clickhouse-macro" },
      payload: {
        // Default to a regular dependabot version bump title
        pull_request: { title: "chore(deps): bump eslint from 8 to 9" },
      },
    };
  });

  it("should NOT add security label for regular dependency version updates", async () => {
    // Execute the script with a standard version bump title
    await labelDependabot(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that addLabels was never triggered
    expect(mockGithub.rest.issues.addLabels).not.toHaveBeenCalled();
  });

  it("should automatically add '🛡️ sec' label if title explicitly contains 'security'", async () => {
    // Inject a security vulnerability patch title into the context payload
    mockContext.payload.pull_request.title = "chore(deps): security patch for tar package";

    await labelDependabot(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the security label was successfully applied to the exact PR
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 202,
      labels: ["🛡️ sec"],
    });
  });

  it("should automatically add '🛡️ sec' label if title contains a CVE code pattern", async () => {
    // Inject a title containing a specific CVE code
    mockContext.payload.pull_request.title = "chore(deps): fix cve-2026-1234 in braces package";

    await labelDependabot(/** @type {any} */ ({ github: mockGithub, context: mockContext }));

    // Verify that the security label was successfully applied
    expect(mockGithub.rest.issues.addLabels).toHaveBeenCalledWith({
      owner: "gigaflux",
      repo: "gflx-clickhouse-macro",
      issue_number: 202,
      labels: ["🛡️ sec"],
    });
  });
});
