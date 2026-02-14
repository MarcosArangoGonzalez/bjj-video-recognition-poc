import React, { useState, useEffect } from 'react';
import VideoUpload from './components/VideoUpload';
import TagDisplay from './components/TagDisplay';
import TagEditor from './components/TagEditor';
import { videoApi } from './services/api';

function App() {
    const [videos, setVideos] = useState([]);
    const [selectedVideo, setSelectedVideo] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadVideos();
    }, []);

    const loadVideos = async () => {
        try {
            const data = await videoApi.getAllVideos();
            setVideos(data);
            if (data.length > 0 && !selectedVideo) {
                setSelectedVideo(data[0]);
            }
        } catch (error) {
            console.error('Failed to load videos:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleUploadComplete = (newVideo) => {
        setVideos([newVideo, ...videos]);
        setSelectedVideo(newVideo);
    };

    const handleTagAdded = () => {
        // Reload selected video to get updated tags
        if (selectedVideo) {
            videoApi.getVideoById(selectedVideo.id).then((updated) => {
                setSelectedVideo(updated);
                setVideos(videos.map((v) => (v.id === updated.id ? updated : v)));
            });
        }
    };

    const getStatusBadge = (status) => {
        const colors = {
            PENDING: 'bg-yellow-100 text-yellow-800',
            PROCESSING: 'bg-blue-100 text-blue-800',
            COMPLETED: 'bg-green-100 text-green-800',
            FAILED: 'bg-red-100 text-red-800',
        };

        return (
            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${colors[status]}`}>
                {status}
            </span>
        );
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-gradient-to-r from-blue-600 to-blue-800 text-white shadow-lg">
                <div className="container mx-auto px-4 py-6">
                    <h1 className="text-3xl font-bold">BJJ Video Recognition PoC</h1>
                    <p className="text-blue-100 mt-1">
                        Automated video analysis with Google Cloud Video Intelligence
                    </p>
                </div>
            </header>

            <main className="container mx-auto px-4 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column: Upload */}
                    <div className="lg:col-span-1">
                        <VideoUpload onUploadComplete={handleUploadComplete} />
                    </div>

                    {/* Middle Column: Video List */}
                    <div className="lg:col-span-1">
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-2xl font-bold mb-4 text-gray-800">Videos</h2>

                            {loading ? (
                                <p className="text-gray-500 text-center py-4">Loading...</p>
                            ) : videos.length === 0 ? (
                                <p className="text-gray-500 text-center py-4">
                                    No videos yet. Upload one to get started!
                                </p>
                            ) : (
                                <div className="space-y-2 max-h-96 overflow-y-auto">
                                    {videos.map((video) => (
                                        <div
                                            key={video.id}
                                            onClick={() => setSelectedVideo(video)}
                                            className={`p-3 rounded-lg cursor-pointer transition-colors ${selectedVideo?.id === video.id
                                                    ? 'bg-blue-50 border-2 border-blue-500'
                                                    : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                                                }`}
                                        >
                                            <div className="flex justify-between items-start mb-1">
                                                <p className="font-medium text-gray-800 truncate flex-1">
                                                    {video.filename}
                                                </p>
                                                {getStatusBadge(video.analysisStatus)}
                                            </div>
                                            <p className="text-xs text-gray-500">
                                                {new Date(video.uploadDate).toLocaleString()}
                                            </p>
                                            <p className="text-xs text-gray-600 mt-1">
                                                {video.tags.length} tag{video.tags.length !== 1 ? 's' : ''}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right Column: Tags */}
                    <div className="lg:col-span-1 space-y-6">
                        {selectedVideo ? (
                            <>
                                <TagDisplay tags={selectedVideo.tags} />
                                <TagEditor
                                    videoId={selectedVideo.id}
                                    onTagAdded={handleTagAdded}
                                />
                            </>
                        ) : (
                            <div className="bg-white rounded-lg shadow-md p-6">
                                <p className="text-gray-500 text-center py-8">
                                    Select a video to view and edit tags
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}

export default App;
