import React, { useState } from 'react';
import { videoApi } from '../services/api';

const VideoUpload = ({ onUploadComplete }) => {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState(null);
    const [dragActive, setDragActive] = useState(false);

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            setSelectedFile(file);
            setError(null);
        }
    };

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setSelectedFile(e.dataTransfer.files[0]);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) {
            setError('Please select a file first');
            return;
        }

        setUploading(true);
        setError(null);
        setUploadProgress(0);

        try {
            const video = await videoApi.uploadVideo(selectedFile, setUploadProgress);
            setSelectedFile(null);
            setUploadProgress(0);
            if (onUploadComplete) {
                onUploadComplete(video);
            }
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to upload video');
            console.error('Upload error:', err);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold mb-4 text-gray-800">Upload BJJ Video</h2>

            <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${dragActive
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input
                    type="file"
                    id="video-upload"
                    className="hidden"
                    accept="video/mp4,video/avi,video/mov,video/mkv"
                    onChange={handleFileSelect}
                    disabled={uploading}
                />

                <label
                    htmlFor="video-upload"
                    className="cursor-pointer flex flex-col items-center"
                >
                    <svg
                        className="w-16 h-16 text-gray-400 mb-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                        />
                    </svg>

                    <p className="text-lg text-gray-700 mb-2">
                        {selectedFile ? selectedFile.name : 'Click to select or drag and drop'}
                    </p>
                    <p className="text-sm text-gray-500">MP4, AVI, MOV, or MKV (max 500MB)</p>
                </label>
            </div>

            {selectedFile && !uploading && (
                <button
                    onClick={handleUpload}
                    className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
                >
                    Upload and Analyze
                </button>
            )}

            {uploading && (
                <div className="mt-4">
                    <div className="flex justify-between mb-2">
                        <span className="text-sm text-gray-600">Uploading...</span>
                        <span className="text-sm text-gray-600">{uploadProgress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${uploadProgress}%` }}
                        />
                    </div>
                </div>
            )}

            {error && (
                <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                    {error}
                </div>
            )}
        </div>
    );
};

export default VideoUpload;
