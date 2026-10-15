/* Destination choices come from active routes in the Django database. */
document.addEventListener('DOMContentLoaded', () => {
  const origin = document.querySelector('[name="from"]');
  const destination = document.querySelector('[name="to"]');
  if (!origin || !destination || origin.tagName !== 'SELECT') return;

  const setOptions = (element, stations, placeholder) => {
    element.replaceChildren(new Option(placeholder, ''));
    stations.forEach(station => element.add(new Option(station.city + ' — ' + station.name, String(station.id))));
  };

  const load = async (url) => {
    const response = await fetch(url, {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error('Unable to load stations');
    return (await response.json()).stations;
  };

  const updateDestinations = async () => {
    destination.disabled = true;
    setOptions(destination, [], 'Choose an origin first');
    if (!origin.value) return;
    try {
      const selectedOrigin = origin.value;
      const stations = await load('/routes/destinations/?origin=' + encodeURIComponent(selectedOrigin));
      if (origin.value !== selectedOrigin) return;
      setOptions(destination, stations, stations.length ? 'Select destination' : 'No direct destinations available');
      destination.disabled = stations.length === 0;
    } catch {
      setOptions(destination, [], 'Could not load destinations');
    }
  };

  load('/routes/origins/').then(stations => {
    setOptions(origin, stations, 'Select origin');
    origin.addEventListener('change', updateDestinations);
    updateDestinations();
  }).catch(() => setOptions(origin, [], 'Could not load stations'));
});
