// Preserve an operator's place when the periodic status refresh redraws the form.
export function captureTextareaScroll(root) {
  return Array.from(root.querySelectorAll("textarea"), (field) => ({
    value: field.value,
    top: field.scrollTop,
    left: field.scrollLeft,
  }));
}

export function restoreTextareaScroll(root, positions) {
  root.querySelectorAll("textarea").forEach((field, index) => {
    const previous = positions[index];
    if (previous && field.value === previous.value) {
      field.scrollTop = previous.top;
      field.scrollLeft = previous.left;
    }
  });
}
