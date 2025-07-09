import api from './api';

export async function fetchNamespaces() {
    const response = await api.get('/api/v1/namespaces/');
    if (response.status !== 200) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.data;
}
