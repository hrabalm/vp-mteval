import api from './api';

export class RunNotFoundError extends Error { }

export const fetchRun = async (runId: string, namespaceId: string) => {
    const run = await api
        .get(`api/v1/namespaces/${namespaceId}/translations-runs/${runId}`)
        .then((r) => r.data)
        .catch((err) => {
            if (err.status === 404) {
                throw new RunNotFoundError(`Run with id "${runId}" not found in namespace "${namespaceId}"`);
            }
            throw err;
        })
    return run;
}

export const fetchRuns = async (namespaceId: string) => {
    return api
        .get(`api/v1/namespaces/${namespaceId}/translations-runs/`)
        .then((r) => r.data)
}
