// @ts-check

/**
 * @param {Omit<import('@actions/github-script').AsyncFunctionArguments, 'github'> & { github: import('@actions/github').GitHub, core: any }} args
 */
module.exports = async ({ github, context, core }) => {
  // Ensure the script executes only within a Pull Request context
  if (!context.payload["pull_request"]) {
    console.log("No pull request found in context.");
    return;
  }

  /** @type {import('@octokit/webhooks-types').PullRequestEvent} */
  const payload = /** @type {any} */ (context.payload);

  // Extract essential PR details directly from the payload to avoid context drift
  const prNumber = payload.pull_request.number;
  const prBody = payload.pull_request.body || "";

  console.log(`Processing PR #${prNumber} based on template checkboxes.`);

  // 1. Setup Label Mappings using safe Unicode hashes
  const labelMapping = {
    "Security Update": "\uD83D\uDEE1\uFE0F sec",
    "New Feature": "\uD83D\uDE80 feature",
    "Bug Fix": "\uD83D\uDC1E bugfix",
    Revert: "\u23EA revert",
    "Performance Improvement": "\u26A1 performance",
    Documentation: "\uD83D\uDCDD docs",
    "CI/CD & Tooling": "\uD83E\uDD16 ci",
    Test: "\uD83E\uDDEA test",
    "Build System or external dependencies": "\uD83D\uDCE6 build",
    Style: "\uD83C\uDFA8 style",
    Refactor: "\u267B\uFE0F refactor",
    Maintenance: "\u2699\uFE0F chore",
  };

  // Define priority weights for prefixes (higher number = higher importance)
  const priorityWeights = {
    "\uD83D\uDEE1\uFE0F sec": 12,
    "\uD83D\uDC1E bugfix": 11,
    "\u23EA revert": 10,
    "\uD83D\uDE80 feature": 9,
    "\u26A1 performance": 8,
    "\u267B\uFE0F refactor": 7,
    "\uD83E\uDD16 ci": 6,
    "\uD83D\uDCE6 build": 5,
    "\uD83E\uDDEA test": 4,
    "\uD83C\uDFA8 style": 3,
    "\uD83D\uDCDD docs": 2,
    "\u2699\uFE0F chore": 1,
  };

  // Mapping from GitHub labels to Conventional Commits prefixes
  const titlePrefixMapping = {
    "\uD83D\uDEE1\uFE0F sec": "sec",
    "\uD83D\uDE80 feature": "feat",
    "\uD83D\uDC1E bugfix": "fix",
    "\u23EA revert": "revert",
    "\u26A1 performance": "perf",
    "\uD83D\uDCDD docs": "docs",
    "\uD83E\uDD16 ci": "ci",
    "\uD83E\uDDEA test": "test",
    "\uD83D\uDCE6 build": "build",
    "\uD83C\uDFA8 style": "style",
    "\u267B\uFE0F refactor": "refactor",
    "\u2699\uFE0F chore": "chore",
  };

  const breakingLabel = "\uD83D\uDEA8 break"; // Unicode for 🚨 break

  // 2. Parse Standard Semantic Type Checkboxes
  const checkboxRegex = /-\s*\[[xX]]\s*\*\*(.*?)\*\*/g;
  /** @type {string[]} */
  const detectedLabels = [];
  let match;

  while ((match = checkboxRegex.exec(prBody)) !== null) {
    const checkboxText = match[1].trim();
    const targetLabel = labelMapping[checkboxText];
    if (targetLabel) {
      detectedLabels.push(targetLabel);
    }
  }

  // 3. Parse Breaking Changes Section
  let isBreaking = false;
  const breakingSectionMatch = prBody.match(
    /##\s*(?:\uD83D\uDEA8|\u26A0\uFE0F)?\s*Breaking Changes[\s\S]*?(?=##|$)/i
  );

  if (breakingSectionMatch) {
    const breakingContent = breakingSectionMatch[0];
    const yesChecked = /-\s*\[[xX]]\s*Yes/i.test(breakingContent);
    const noChecked = /-\s*\[[xX]]\s*No/i.test(breakingContent);

    if (yesChecked && !noChecked) {
      isBreaking = true;
      detectedLabels.push(breakingLabel);
    }
  }

  console.log("Detected labels (including breaking):", detectedLabels);

  // 4. Manage GitHub Labels via API
  const { data: existingLabels } = await github.rest.issues.listLabelsOnIssue({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  const existingLabelNames = existingLabels.map((l) => l.name);
  const allManagedLabels = [...Object.values(labelMapping), breakingLabel];

  // Remove outdated labels
  for (const label of existingLabelNames) {
    if (allManagedLabels.includes(label) && !detectedLabels.includes(label)) {
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

  // Add newly checked labels
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

  // 5. Fetch all comments to manage validation logs
  const { data: comments } = await github.rest.issues.listComments({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: prNumber,
  });

  // 6. Validate that at least one semantic type was selected
  const selectedTypes = detectedLabels.filter((l) => l !== breakingLabel);
  const validationComment = comments.find(
    (comment) =>
      comment.user?.type?.toLowerCase() === "bot" &&
      comment.body?.includes("Please select at least one Type of Change")
  );

  if (selectedTypes.length === 0) {
    const warningMessage = `## \u26A0\uFE0F Action Required: Missing Change Type\n\n@${payload.pull_request.user.login}, please select at least one **Type of Change** in your PR description checkboxes so that we can properly categorize this change and update the PR title.`;

    if (!validationComment) {
      console.log("No validation comment found. Creating a new one.");
      await github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: prNumber,
        body: warningMessage,
      });
    }

    core.setFailed("Validation failed: No 'Type of Change' was selected in the PR description.");
    return;
  }

  // If validation passes, clean up any old warning comments
  if (validationComment) {
    console.log(`Deleting old type-validation comment with ID: ${validationComment.id}`);
    await github.rest.issues.deleteComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      comment_id: validationComment.id,
    });
  }

  // 7. Update PR Title based on priorities and Breaking Status
  const highestPriorityLabel = selectedTypes.sort((a, b) => {
    return (priorityWeights[b] || 0) - (priorityWeights[a] || 0);
  })[0];

  const newPrefix = titlePrefixMapping[highestPriorityLabel];

  if (newPrefix) {
    const currentTitle = payload.pull_request.title.trim();
    const matchTitle = currentTitle.match(/^[a-zA-Z]+(\([^)]+\))?(!)?\s*:\s*(.*)$/);

    let expectedTitle;
    const breakingBang = isBreaking ? "!" : "";

    if (matchTitle) {
      const scope = matchTitle[1] || "";
      const cleanTitleText = matchTitle[3];
      expectedTitle = `${newPrefix}${scope}${breakingBang}: ${cleanTitleText}`;
    } else {
      expectedTitle = `${newPrefix}${breakingBang}: ${currentTitle}`;
    }

    if (currentTitle !== expectedTitle) {
      console.log(`Updating PR title. From "${currentTitle}" to "${expectedTitle}"`);
      await github.rest.pulls.update({
        owner: context.repo.owner,
        repo: context.repo.repo,
        pull_number: prNumber,
        title: expectedTitle,
      });
    }
  }

  // 8. Delete old bot validation comments (release notes warning)
  const botComment = comments.find(
    (comment) =>
      comment.user?.type?.toLowerCase() === "bot" &&
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
};
