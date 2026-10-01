// Keep the DOM node being edited (including the login field) until focus leaves it.
export function shouldDeferPresenterRefresh(root, activeElement) {
  return Boolean(
    activeElement
    && root.contains(activeElement)
    && activeElement.matches("input, textarea, select")
  );
}
