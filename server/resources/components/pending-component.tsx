import { Spinner } from '@/components/ui/spinner';

export function PendingComponent() {
    return (
        <div className="flex items-center justify-center h-full">
            <Spinner size="large">Loading run data...</Spinner>
        </div>
    );
}