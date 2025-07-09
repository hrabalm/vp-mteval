import PageHeading from '@/components/PageHeading';
import { createFileRoute } from '@tanstack/react-router';
import ReactMarkdown from 'react-markdown';

export const Route = createFileRoute('/')({
  component: Index,
})

const markdownContent = `
### Introduction

### Documentation

Nice page content written in Markdown.
`;

function Index() {
  return (
    <>
      <PageHeading>Home</PageHeading>
      <div className="prose dark:prose-invert max-w-none">
        <ReactMarkdown>{markdownContent}</ReactMarkdown>
      </div>
    </>
  )
}