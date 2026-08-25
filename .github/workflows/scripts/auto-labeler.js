// @ts-check

// --- MONOLITHIC REGULAR EXPRESSION PATTERN ---
// Group 1: Captures the checkbox status (either an 'x'/'X' or just spaces)
// Group 2: Strictly extracts any content enclosed between double asterisks (the exact label name)
const PR_TEMPLATE_CHECKBOX_REGEX = /^\s*-\s*\[([xX]|\s*)]\s*\*\*(.*?)\*\*/;

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
  const prBody = payload.pull_request.body || "";

  console.log(`Synchronizing GitHub labels for PR #${prNumber} based on template checkboxes.`);

  const prBodyLines = prBody.split(/\r?\n/);
  /** @type {string[]} */
  const detectedLabels = [];
  /** @type {string[]} */
  const allTemplateLabels = [];

  // 1. Single pass to parse ALL potential and checked labels from the template
  for (const line of prBodyLines) {
    const match = line.match(PR_TEMPLATE_CHECKBOX_REGEX);

    if (match) {
      const checkboxStatus = match[1].toLowerCase(); // Contains 'x' or ' '
      const extractedLabel = match[2].trim(); // The exact label string inside asterisks

      // Register every found label in the master template list to manage automated rollbacks
      allTemplateLabels.push(extractedLabel);

      // Collect only the active/checked labels
      if (checkboxStatus === "x") {
        detectedLabels.push(extractedLabel);
      }
    }
  }

  console.log("Detected active labels:", detectedLabels);
  console.log("All managed template labels:", allTemplateLabels);

  // 2. Fetch existing labels currently applied to the PR on GitHub
  const { data: existingLabels } = await github.rest.issues.listLabelsOnIssue({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  const existingLabelNames = existingLabels.map((l) => l.name);

  // 3. Remove outdated labels (only if they are part of our managed template checkboxes)
  for (const label of existingLabelNames) {
    if (allTemplateLabels.includes(label) && !detectedLabels.includes(label)) {
      try {
        await github.rest.issues.removeLabel({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: prNumber,
          name: label,
        });
        console.log(`Removed outdated label: ${label}`);
      } catch (e) {
        // @ts-ignore
        console.log(`Failed to remove label ${label}: ${e.message}`);
      }
    }
  }

  // 4. Add newly checked labels to the PR
  for (const targetLabel of detectedLabels) {
    if (!existingLabelNames.includes(targetLabel)) {
      console.log(`Adding label: "${targetLabel}"`);
      await github.rest.issues.addLabels({
        issue_number: prNumber,
        owner: context.repo.owner,
        repo: context.repo.repo,
        labels: [targetLabel],
      });
    }
  }

  // 5. Clean up old bot validation comments left by previous workflow iterations if any exist
  const { data: comments } = await github.rest.issues.listComments({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  const botComments = comments.filter(
    (comment) =>
      comment.user?.type?.toLowerCase() === "bot" &&
      (comment.body?.includes("Please select at least one Type of Change") ||
        comment.body?.includes("automated release notes generation"))
  );

  for (const comment of botComments) {
    console.log(`Cleaning up historical validation comment with ID: ${comment.id}`);
    try {
      await github.rest.issues.deleteComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        comment_id: comment.id,
      });
    } catch (e) {
      // @ts-ignore
      console.log(`Failed to delete comment ${comment.id}: ${e.message}`);
    }
  }
};
