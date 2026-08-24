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

  const title = payload.pull_request.title.trim();
  const labelMapping = {
    sec: "🛡️ sec",
    security: "🛡️ sec",
    feat: "🚀 feature",
    feature: "🚀 feature",
    enhance: "🚀 feature",
    enhancement: "🚀 feature",
    fix: "🐞 bugfix",
    bugfix: "🐞 bugfix",
    revert: "⏪ revert",
    undo: "⏪ revert",
    perf: "⚡ performance",
    performance: "⚡ performance",
    doc: "📝 docs",
    docs: "📝 docs",
    documentation: "📝 docs",
    ci: "🤖 ci",
    cicd: "🤖 cicd",
    test: "🧪 test",
    build: "📦 build",
    dep: "📦 dep",
    deps: "📦 deps",
    dependencies: "📦 dependencies",
    style: "🎨 style",
    format: "🎨 style",
    refactor: "♻️ refactor",
    chore: "⚙️ chore",
  };

  const match = title.match(/^([a-zA-Z]+)(?:\([^)]+\))?!?\s*:/);

  if (match) {
    const prType = match[1].toLowerCase();
    const targetLabel = labelMapping[prType];

    if (targetLabel) {
      const { data: existingLabels } = await github.rest.issues.listLabelsOnIssue({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
      });

      const existingLabelNames = existingLabels.map((l) => l.name);
      const allPossibleLabels = Object.values(labelMapping);

      for (const label of existingLabelNames) {
        if (allPossibleLabels.includes(label) && label !== targetLabel) {
          try {
            await github.rest.issues.removeLabel({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              name: label,
            });
            console.log(`Removed old label: ${label}`);
          } catch (e) {
            // @ts-ignore
            console.log(`Failed to remove label ${label}: ${e.message}`);
          }
        }
      }

      if (!existingLabelNames.includes(targetLabel)) {
        console.log(`Adding label "${targetLabel}" for PR type "${prType}"`);
        await github.rest.issues.addLabels({
          issue_number: context.issue.number,
          owner: context.repo.owner,
          repo: context.repo.repo,
          labels: [targetLabel],
        });
      }

      const { data: comments } = await github.rest.issues.listComments({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
      });

      const botComment = comments.find(
        (comment) =>
          comment.user?.type === "Bot" &&
          comment.body?.includes("automated release notes generation")
      );

      if (botComment) {
        console.log(`Deleting old validation comment with ID: ${botComment.id}`);
        await github.rest.issues.deleteComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          comment_id: botComment.id,
        });
      }
    } else {
      console.log(`No label mapping found for type: ${prType}`);
    }
  } else {
    console.log("Could not parse PR type from title.");
  }
};
