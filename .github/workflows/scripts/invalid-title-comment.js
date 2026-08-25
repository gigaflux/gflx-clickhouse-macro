// @ts-check

/**
 * @param {Omit<import('@actions/github-script').AsyncFunctionArguments, 'github'> & { github: import('@actions/github').GitHub }} args
 */
module.exports = async ({ github, context }) => {
  if (!context.payload["pull_request"]) {
    console.log("No pull request found in context.");
    return;
  }

  /** @type {import('@octokit/webhooks-types').PullRequestEvent} */
  const payload = /** @type {any} */ (context.payload);

  const prNumber = payload.pull_request.number;
  const user = payload.pull_request.user.login;

  // Formulate the message using safe Unicode escape sequences for all emojis
  const message = `\uD83D\uDC4B Hi @${user}!

Our project uses automated release notes generation based on PR titles. To proceed, please update your PR title to match the [Conventional Commits standard](https://github.com).
\uD83D\uDCA1 _If your change introduces a Breaking Change, add an exclamation mark before the colon, e.g., \`feat!: major breaking update\`_
Once you rename the title, this check will automatically re-run. Thank you for your contribution! \uD83E\uDD1D`;

  // Post the comment using the fully stabilized PR number variables
  await github.rest.issues.createComment({
    issue_number: prNumber,
    owner: context.repo.owner,
    repo: context.repo.repo,
    body: message,
  });
};
