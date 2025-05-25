import api from './api';

export class RunNotFoundError extends Error { }

export const fetchRun = async (runId: string) => {
    const run = await api
        .get(`api/v1/translations-runs/${runId}`)
        .then((r) => r.data)
        .catch((err) => {
            if (err.status = 404) {
                throw new RunNotFoundError(`Run with id "${runId}" not found`);
            }
            throw err;
        })
    return run;
}

export const fetchRuns = async () => {
    return api
        .get('api/v1/runs')
        .then((r) => r.data)
}
