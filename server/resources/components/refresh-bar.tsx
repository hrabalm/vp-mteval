import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import React, { useState, useEffect } from "react";
export default function RefreshBar(
    props: {
        onRefresh: () => void
        isRefreshing: boolean
    }
) {
    const { onRefresh, isRefreshing } = props
    const [refresh, setRefresh] = useState(isRefreshing);
    const period = 1000; // 1 second

    useEffect(() => {
        setRefresh(isRefreshing);
    }, [isRefreshing]);

    useEffect(() => {
        if (!refresh) return;

        const interval = setInterval(() => {
            onRefresh();
        }, period);

        // Cleanup on unmount
        return () => clearInterval(interval);
    }, [refresh, onRefresh]);

    return (
        <div className="flex items-center space-x-2">
            <Switch
                checked={refresh}
                onCheckedChange={setRefresh}
                aria-label="Toggle refresh"
            />
            <Label>Auto-refresh</Label>
        </div>
    )
}
