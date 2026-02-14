import axios from 'axios';

const API_BASE_URL = '/api';

export const videoApi = {
    // Upload video
    uploadVideo: async (file, onProgress) => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post(`${API_BASE_URL}/videos/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    onProgress(percentCompleted);
                }
            },
        });

        return response.data;
    },

    // Get all videos
    getAllVideos: async () => {
        const response = await axios.get(`${API_BASE_URL}/videos`);
        return response.data;
    },

    // Get video by ID
    getVideoById: async (id) => {
        const response = await axios.get(`${API_BASE_URL}/videos/${id}`);
        return response.data;
    },

    // Delete video
    deleteVideo: async (id) => {
        await axios.delete(`${API_BASE_URL}/videos/${id}`);
    },
};

export const tagApi = {
    // Get tags for a video
    getVideoTags: async (videoId) => {
        const response = await axios.get(`${API_BASE_URL}/videos/${videoId}/tags`);
        return response.data;
    },

    // Add manual tag
    addTag: async (videoId, tagName, timestampSeconds) => {
        const response = await axios.post(`${API_BASE_URL}/videos/${videoId}/tags`, {
            tagName,
            timestampSeconds,
        });
        return response.data;
    },

    // Update tag
    updateTag: async (videoId, tagId, tagName, timestampSeconds) => {
        const response = await axios.put(
            `${API_BASE_URL}/videos/${videoId}/tags/${tagId}`,
            {
                tagName,
                timestampSeconds,
            }
        );
        return response.data;
    },

    // Delete tag
    deleteTag: async (videoId, tagId) => {
        await axios.delete(`${API_BASE_URL}/videos/${videoId}/tags/${tagId}`);
    },

    // Search tags
    searchTags: async (query) => {
        const response = await axios.get(`${API_BASE_URL}/videos/0/tags/search`, {
            params: { q: query },
        });
        return response.data;
    },
};
