import { useParams } from 'react-router-dom';

export default function VideoDetail() {
  const { id } = useParams();

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Video Details</h1>
      <p className="text-gray-500">
        Video ID: {id}
      </p>
      <p className="text-sm text-gray-400 mt-2">
        (Video detail view with transcript will be implemented in Phase 5)
      </p>
    </div>
  );
}
