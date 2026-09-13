/**
 * Offline IndexedDB Storage Queue for No-Wi-Fi Warehouse Operation.
 */
const DB_NAME = 'LegalMetrologyOfflineDB';
const DB_VERSION = 1;
const STORE_SCANS = 'offline_scans';

class OfflineStore {
  constructor() {
    this.db = null;
    this.initDB();
  }

  async initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_SCANS)) {
          db.createObjectStore(STORE_SCANS, { keyPath: 'id', autoIncrement: true });
        }
      };
      request.onsuccess = (e) => {
        this.db = e.target.result;
        resolve(this.db);
      };
      request.onerror = (e) => {
        console.error('IndexedDB error:', e);
        reject(e);
      };
    });
  }

  async saveScanOffline(scanData) {
    if (!this.db) await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(STORE_SCANS, 'readwrite');
      const store = tx.objectStore(STORE_SCANS);
      const entry = {
        ...scanData,
        queued_at: new Date().toISOString(),
        synced: false
      };
      const req = store.add(entry);
      req.onsuccess = () => resolve(req.result);
      req.onerror = (e) => reject(e);
    });
  }

  async getPendingScans() {
    if (!this.db) await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(STORE_SCANS, 'readonly');
      const store = tx.objectStore(STORE_SCANS);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result.filter(item => !item.synced));
      req.onerror = (e) => reject(e);
    });
  }

  async markScanSynced(id) {
    if (!this.db) await this.initDB();
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(STORE_SCANS, 'readwrite');
      const store = tx.objectStore(STORE_SCANS);
      const req = store.delete(id);
      req.onsuccess = () => resolve(true);
      req.onerror = (e) => reject(e);
    });
  }
}

window.offlineStore = new OfflineStore();
