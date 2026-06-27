(function () {
  function installOverride() {
    if (!window.L || !L.tileLayer || !L.tileLayer.wms) return false;
    const originalWms = L.tileLayer.wms.bind(L.tileLayer);
    L.tileLayer.wms = function (url, options) {
      if (String(url).includes("kaart.maaamet.ee/wms/alus-geo")) {
        return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        });
      }
      return originalWms(url, options);
    };
    window.__osmBasemapOverrideInstalled = true;
    return true;
  }

  if (!installOverride()) {
    window.addEventListener("load", installOverride, { once: true });
  }
})();
