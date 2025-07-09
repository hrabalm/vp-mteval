import api from './api';

export class DatasetNotFoundError extends Error { }

export const fetchDataset = async (datasetId: string, namespaceId: string) => {
    const dataset = await api
        .get(`api/v1/namespaces/${namespaceId}/datasets/${datasetId}`)
        .then((r) => r.data)
        .catch((err) => {
            if (err.status === 404) {
                throw new DatasetNotFoundError(`Dataset with id "${datasetId}" not found in namespace "${namespaceId}"`);
            }
            throw err;
        })
    return dataset;
}

export const fetchDatasets = async (namespaceId: string) => {
    return api
        .get(`api/v1/namespaces/${namespaceId}/datasets/`)
        .then((r) => r.data)
}
