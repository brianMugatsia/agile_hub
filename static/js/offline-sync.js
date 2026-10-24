/**
 * Agile Hub Offline Sync (IndexedDB + Service Worker integration)
 */
(function() {
  const DB_NAME = 'agile_hub_offline_db';
  const STORE_NAME = 'offline_queue';
  const DB_VERSION = 1;

  function openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        }
      };
      request.onsuccess = (event) => resolve(event.target.result);
      request.onerror = (event) => reject(event.target.error);
    });
  }

  async function queueOfflineRequest(url, method, formDataObj, csrfToken) {
    try {
      const db = await openDB();
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.add({
          url: url,
          method: method,
          data: formDataObj,
          csrfToken: csrfToken,
          timestamp: new Date().toISOString()
        });
        request.onsuccess = () => {
          showOfflineBanner(`Action saved offline. Will sync when reconnected.`);
          resolve(true);
        };
        request.onerror = (e) => reject(e.target.error);
      });
    } catch (err) {
      console.error('Failed to queue offline request:', err);
    }
  }

  async function syncQueue() {
    if (!navigator.onLine) return;
    try {
      const db = await openDB();
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const getAllRequest = store.getAll();

      getAllRequest.onsuccess = async () => {
        const items = getAllRequest.result;
        if (!items || items.length === 0) return;

        console.log(`Syncing ${items.length} offline transactions...`);
        for (const item of items) {
          try {
            const response = await fetch(item.url, {
              method: item.method || 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': item.csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
              },
              body: JSON.stringify(item.data)
            });

            if (response.ok) {
              // Remove from queue
              const deleteTx = db.transaction(STORE_NAME, 'readwrite');
              deleteTx.objectStore(STORE_NAME).delete(item.id);
            }
          } catch (err) {
            console.error('Sync error for item:', item.id, err);
          }
        }
        showOfflineBanner('All offline transactions synchronized successfully!');
      };
    } catch (err) {
      console.error('Error reading offline queue:', err);
    }
  }

  function showOfflineBanner(message) {
    let banner = document.getElementById('offline-sync-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'offline-sync-banner';
      banner.style.cssText = 'position:fixed;bottom:1rem;right:1rem;background:#123568;color:#fff;padding:0.75rem 1.25rem;border-radius:0.5rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:9999;font-size:0.875rem;transition:opacity 0.3s;';
      document.body.appendChild(banner);
    }
    banner.textContent = message;
    banner.style.display = 'block';
    setTimeout(() => {
      banner.style.opacity = '0';
      setTimeout(() => banner.style.display = 'none', 300);
    }, 4000);
  }

  window.addEventListener('online', () => {
    showOfflineBanner('Network connection restored. Syncing offline data...');
    syncQueue();
  });

  window.addEventListener('offline', () => {
    showOfflineBanner('You are currently offline. Actions will be saved locally.');
  });

  // Intercept form submissions if offline
  document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('form[data-offline-queue]');
    forms.forEach(form => {
      form.addEventListener('submit', async (e) => {
        if (!navigator.onLine) {
          e.preventDefault();
          const formData = new FormData(form);
          const dataObj = {};
          formData.forEach((value, key) => { dataObj[key] = value; });
          const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
          const action = form.getAttribute('action') || window.location.href;
          const method = form.getAttribute('method') || 'POST';

          await queueOfflineRequest(action, method, dataObj, csrfToken);
          form.reset();
        }
      });
    });
  });
})();
