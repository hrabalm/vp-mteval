export default function PageHeading({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {children}
            </h2>
        </div>
    );
}