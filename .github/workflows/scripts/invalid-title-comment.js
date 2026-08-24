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

  const user = payload.pull_request.user.login;
  const message = `👋 Hi @${user}!

Our project uses automated release notes generation based on PR titles. To proceed, please update your PR title to match the [Conventional Commits standard](https://github.com).

Please edit your PR title using one of the permitted prefixes mapped to your **Type of Change** selection (ensure there is a colon and a space after it):

* 🛡️ **Security Update:** \`sec: description\` or \`security: description\`
* 🚀 **New Feature:** \`feat: description\` or \`feature: description\`
* 🐞 **Bug Fix:** \`fix: description\` or \`bugfix: description\`
* ⏪ **Revert:** \`revert: description\` or \`undo: description\`
* ⚡ **Performance Improvement:** \`perf: description\` or \`performance: description\`
* 📝 **Documentation:** \`docs: description\` or \`documentation: description\`
* 🤖 **CI/CD & Tooling:** \`ci: description\` or \`cicd: description\`
* 🧪 **Test:** \`test: description\`
* 📦 **Build System & Dependencies:** \`build: description\`, \`dep: description\`, or \`deps: description\`
* 🎨 **Style:** \`style: description\` or \`format: description\`
* ♻️ **Refactor:** \`refactor: description\`
* ⚙️ **Maintenance:** \`chore: description\`

💡 _If your change introduces a Breaking Change, add an exclamation mark before the colon, e.g., \`feat!: major breaking update\`_

Once you rename the title, this check will automatically re-run. Thank you for your contribution! 🤝`;

  await github.rest.issues.createComment({
    issue_number: context.issue.number,
    owner: context.repo.owner,
    repo: context.repo.repo,
    body: message,
  });
};
