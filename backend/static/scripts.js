async function fetchItems(search = '') {
  const res = await fetch(`/items?search=${encodeURIComponent(search)}`);
  const items = await res.json();
  renderItems(items);
}
