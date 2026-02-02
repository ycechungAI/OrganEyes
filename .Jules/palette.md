## 2024-05-23 - Missing ARIA Labels on Icon-Only Buttons
**Learning:** The UI relies heavily on icon-only buttons (like "X" for close/remove) without text labels. While visually clear, these are inaccessible to screen readers which will just read "button".
**Action:** Systematically audit all icon-only buttons and add descriptive `aria-label` attributes that explain the action (e.g., "Remove Work Projects" instead of just "Remove").
