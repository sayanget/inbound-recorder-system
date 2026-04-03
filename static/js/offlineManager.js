/**
 * 离线数据管理器
 * 使用IndexedDB存储离线录入的数据,并在网络恢复时同步到服务器
 */

class OfflineManager {
    constructor() {
        this.dbName = 'InboundOfflineDB';
        this.dbVersion = 1;
        this.db = null;
        this.syncInProgress = false;
    }

    /**
     * 初始化IndexedDB数据库
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('IndexedDB打开失败:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('IndexedDB初始化成功');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // 创建待同步记录存储
                if (!db.objectStoreNames.contains('pendingRecords')) {
                    const store = db.createObjectStore('pendingRecords', { keyPath: 'id' });
                    store.createIndex('type', 'type', { unique: false });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    store.createIndex('synced', 'synced', { unique: false });
                }

                console.log('IndexedDB数据库升级完成');
            };
        });
    }

    /**
     * 生成UUID
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * 保存离线数据
     * @param {string} type - 数据类型 ('inbound' 或 'sorting')
     * @param {object} data - 要保存的数据
     */
    async saveOffline(type, data) {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pendingRecords'], 'readwrite');
            const store = transaction.objectStore('pendingRecords');

            const record = {
                id: this.generateUUID(),
                type: type,
                data: data,
                timestamp: new Date().toISOString(),
                synced: 0,
                retryCount: 0
            };

            const request = store.add(record);

            request.onsuccess = () => {
                console.log('离线数据保存成功:', record.id);
                resolve(record);
            };

            request.onerror = () => {
                console.error('离线数据保存失败:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * 获取所有待同步记录
     */
    async getPendingRecords() {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pendingRecords'], 'readonly');
            const store = transaction.objectStore('pendingRecords');
            const index = store.index('synced');
            const request = index.getAll(0);

            request.onsuccess = () => {
                resolve(request.result);
            };

            request.onerror = () => {
                console.error('获取待同步记录失败:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * 获取待同步记录数量
     */
    async getPendingCount() {
        const records = await this.getPendingRecords();
        return records.length;
    }

    /**
     * 删除已同步的记录
     * @param {string} id - 记录ID
     */
    async deleteRecord(id) {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pendingRecords'], 'readwrite');
            const store = transaction.objectStore('pendingRecords');
            const request = store.delete(id);

            request.onsuccess = () => {
                console.log('记录删除成功:', id);
                resolve();
            };

            request.onerror = () => {
                console.error('记录删除失败:', request.error);
                reject(request.error);
            };
        });
    }

    /**
     * 更新记录的重试次数
     */
    async updateRetryCount(id, retryCount) {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pendingRecords'], 'readwrite');
            const store = transaction.objectStore('pendingRecords');
            const getRequest = store.get(id);

            getRequest.onsuccess = () => {
                const record = getRequest.result;
                if (record) {
                    record.retryCount = retryCount;
                    const updateRequest = store.put(record);

                    updateRequest.onsuccess = () => resolve();
                    updateRequest.onerror = () => reject(updateRequest.error);
                } else {
                    reject(new Error('记录不存在'));
                }
            };

            getRequest.onerror = () => reject(getRequest.error);
        });
    }

    /**
     * 同步单条记录到服务器
     */
    async syncRecord(record) {
        const endpoint = record.type === 'inbound' ? '/api/record' : '/api/sorting_record';

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(record.data)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (result.success || result.record_id) {
                // 同步成功,删除本地记录
                await this.deleteRecord(record.id);
                return { success: true, record: record };
            } else {
                throw new Error(result.error || '同步失败');
            }
        } catch (error) {
            console.error('同步记录失败:', record.id, error);

            // 更新重试次数
            await this.updateRetryCount(record.id, record.retryCount + 1);

            return { success: false, record: record, error: error.message };
        }
    }

    /**
     * 同步所有待同步记录到服务器
     * @param {function} progressCallback - 进度回调函数
     */
    async syncToServer(progressCallback) {
        if (this.syncInProgress) {
            console.log('同步正在进行中...');
            return { success: false, message: '同步正在进行中' };
        }

        this.syncInProgress = true;

        try {
            const pendingRecords = await this.getPendingRecords();

            if (pendingRecords.length === 0) {
                this.syncInProgress = false;
                return { success: true, message: '没有待同步的数据', synced: 0, failed: 0 };
            }

            console.log(`开始同步 ${pendingRecords.length} 条记录...`);

            let syncedCount = 0;
            let failedCount = 0;
            const failedRecords = [];

            for (let i = 0; i < pendingRecords.length; i++) {
                const record = pendingRecords[i];

                // 调用进度回调
                if (progressCallback) {
                    progressCallback({
                        current: i + 1,
                        total: pendingRecords.length,
                        record: record
                    });
                }

                const result = await this.syncRecord(record);

                if (result.success) {
                    syncedCount++;
                } else {
                    failedCount++;
                    failedRecords.push({
                        record: record,
                        error: result.error
                    });
                }

                // 添加小延迟,避免服务器压力过大
                await new Promise(resolve => setTimeout(resolve, 100));
            }

            this.syncInProgress = false;

            return {
                success: true,
                synced: syncedCount,
                failed: failedCount,
                failedRecords: failedRecords
            };
        } catch (error) {
            console.error('同步过程出错:', error);
            this.syncInProgress = false;
            return { success: false, error: error.message };
        }
    }

    /**
     * 清除所有离线数据
     */
    async clearAll() {
        if (!this.db) {
            await this.init();
        }

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['pendingRecords'], 'readwrite');
            const store = transaction.objectStore('pendingRecords');
            const request = store.clear();

            request.onsuccess = () => {
                console.log('所有离线数据已清除');
                resolve();
            };

            request.onerror = () => {
                console.error('清除离线数据失败:', request.error);
                reject(request.error);
            };
        });
    }
}

// 创建全局实例
const offlineManager = new OfflineManager();

// 页面加载时初始化
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', async () => {
        try {
            await offlineManager.init();
            console.log('离线管理器初始化完成');
        } catch (error) {
            console.error('离线管理器初始化失败:', error);
        }
    });
}
