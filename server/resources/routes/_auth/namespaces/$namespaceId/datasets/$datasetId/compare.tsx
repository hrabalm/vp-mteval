import { createFileRoute, useSearch } from '@tanstack/react-router'
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { TypographyH3, TypographyH4, TypographyH5 } from '@/components/typography'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useState } from 'react';
import { fetchRun } from '@/runs';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from 'recharts';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PendingComponent } from '@/components/pending-component';

type CompareSearch = {
  runAId: number
  runBId: number
}

export const Route = createFileRoute(
  '/_auth/namespaces/$namespaceId/datasets/$datasetId/compare',
)({
  validateSearch: (search: Record<string, unknown>): CompareSearch => {
    return {
      runAId: Number(search?.runAId),
      runBId: Number(search?.runBId),
    }
  },
  loaderDeps: ({ search: { runAId, runBId } }) => ({ runAId, runBId }),
  loader: async ({ deps: { runAId, runBId }, params: { namespaceId } }) => {
    const runA = await fetchRun(runAId.toString(), namespaceId);
    const runB = await fetchRun(runBId.toString(), namespaceId);
    return {
      runA: runA,
      runB: runB,
    }
  },
  component: RouteComponent,
  pendingComponent: PendingComponent,
})

function CompareOverview() {
  const search = Route.useSearch();

  let [selectedMetric, setSelectedMetric] = useState();

  const { runA, runB } = Route.useLoaderData();

  if (runA.dataset.id != runB.dataset.id) {
    throw new Error("Cannot compare runs from different datasets!")
  }

  return <>
    <div className="grid grid-cols-2 gap-4">
      <div className="p-4">
        <TypographyH3>Run A (id={runA.id})</TypographyH3>
      </div>
      <div className="p-4">
        <TypographyH3>Run B (id={runB.id})</TypographyH3>
      </div>
      <div className="p-4 col-span-2">
        <ConfigTable runA={runA} runB={runB} />
      </div>
      <div className="p-4 col-span-2">
        <MetricsTable runA={runA} runB={runB} />
      </div>
    </div>
    <MetricsCharts runA={runA} runB={runB} />
  </>
}

function ConfigTable({ runA, runB }) {
  const allKeys: string[] = Array.from(new Set(Object.keys(runA.config)).union(new Set(Object.keys(runB.config)))).sort()
  return <>
    <TypographyH4>Config</TypographyH4>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Run A</TableHead>
          <TableHead>Run B</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {allKeys.map((key) => {
          return <>
            <TableRow>
              <TableCell>{key}</TableCell>
              <TableCell>{JSON.stringify(runA.config[key])}</TableCell>
              <TableCell>{JSON.stringify(runB.config[key])}</TableCell>
            </TableRow>
          </>
        })}
      </TableBody>
    </Table>
  </>
}

function MetricsTable({ runA, runB }) {
  const extractMetrics = (run: any): string[] => {
    return Object.values(run.dataset_metrics).reduce((acc: string[], value: any) => {
      if (value?.name) {
        acc.push(value.name);
      }
      return acc;
    }, []);
  };
  const allMetrics: string[] = Array.from(new Set([...extractMetrics(runA), ...extractMetrics(runB)])).sort()

  const runAMetricByName = Object.fromEntries(
    Object.entries(runA.dataset_metrics).map(([key, value]) => [value.name, value])
  );
  const runBMetricByName = Object.fromEntries(
    Object.entries(runB.dataset_metrics).map(([key, value]) => [value.name, value])
  );

  return <>
    <TypographyH4>Metrics</TypographyH4>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Run A</TableHead>
          <TableHead>Run B</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {allMetrics.map((metric) => {
          return <>
            <TableRow>
              <TableCell>{metric}</TableCell>
              <TableCell>{runAMetricByName[metric]?.score.toFixed(4)}</TableCell>
              <TableCell>{runBMetricByName[metric]?.score.toFixed(4)}</TableCell>
            </TableRow>
          </>
        })}
      </TableBody>
    </Table>
  </>
}

function MetricSelect({ value, onValueChange, metrics }: { value: any, onValueChange: any, metrics: string[] }) {
  return <>
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="Select a metric" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Available Metrics</SelectLabel>
          {
            metrics.map((metric) => {
              return <SelectItem value={metric}>{metric}</SelectItem>
            })
          }
        </SelectGroup>
      </SelectContent>
    </Select>
  </>
}

function MetricsCharts({ runA, runB }) {
  const commonMetrics = Array.from(new Set(Object.keys(runA.segment_metrics)).intersection(new Set(Object.keys(runB.segment_metrics)))).sort();
  if (commonMetrics.length === 0) {
    return <TypographyH4>No common metrics found between the two runs.</TypographyH4>
  }
  const [selectedMetric, setSelectedMetric] = useState(commonMetrics[0]);

  const runAData = runA.segment_metrics[selectedMetric]?.map((d) => { return { score: d.score } }) || []
  const runBData = runB.segment_metrics[selectedMetric]?.map((d) => { return { score: d.score } }) || []

  const minScore = Math.min(...runAData.map(d => d.score), ...runBData.map(d => d.score))
  const maxScore = Math.max(...runAData.map(d => d.score), ...runBData.map(d => d.score))

  const BINS = 20;
  const binWidth = (maxScore - minScore) / (BINS);
  const bins = Array.from({ length: BINS }, (_, i) => minScore + i * binWidth);

  const runAHist = bins.map((b, i) => {
    const isLast = (i === bins.length - 1);
    return {
      x: b,
      y: runAData.filter(d => {
        if (isLast) {
          // include the maxScore
          return d.score >= b && d.score <= maxScore;
        } else {
          return d.score >= b && d.score < (b + binWidth);
        }
      }).length
    };
  });

  const runBHist = bins.map((b, i) => {
    const isLast = (i === bins.length - 1);
    return {
      x: b,
      y: runBData.filter(d => {
        if (isLast) {
          return d.score >= b && d.score <= maxScore;
        } else {
          return d.score >= b && d.score < (b + binWidth);
        }
      }).length
    };
  });


  const data = runAHist.map((d, i) => {
    return {
      name: d.x.toFixed(2),
      "Run A": d.y,
      "Run B": runBHist[i].y,
    }
  })

  const deltaData = data.map((d) => {
    return {
      name: d.name,
      "Run A": d["Run A"],
      "Run B": d["Run B"],
      "Run A-Run B": d["Run A"] - d["Run B"],
    }
  })

  return <>
    <TypographyH4>Charts</TypographyH4>
    <MetricSelect
      value={selectedMetric}
      onValueChange={setSelectedMetric}
      metrics={commonMetrics}
    />
    <TypographyH5>Segment-level {selectedMetric} histogram</TypographyH5>
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <ReferenceLine y={0} stroke="#000" />
          <Bar dataKey="Run A" fill="#8884d8" />
          <Bar dataKey="Run B" fill="#82ca9d" />
        </BarChart>
      </ResponsiveContainer>
    </div>
    <TypographyH5>Segment-level Δ-{selectedMetric} histogram</TypographyH5>
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={deltaData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <ReferenceLine y={0} stroke="#000" />
          <Bar dataKey="Run A-Run B" fill="#ff7300" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </>
}

function RouteComponent() {
  return (
    <>
      <CompareOverview />
    </>
  )
}
