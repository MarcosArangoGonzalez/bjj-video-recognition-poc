import React, { useState } from 'react';
import { tagApi } from '../services/api';

const TagEditor = ({ videoId, onTagAdded, onTagDeleted }) => {
    const [tagName, setTagName] = useState('');
    const [timestamp, setTimestamp] = useState('');
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState(null);

    const handleAddTag = async (e) => {
        e.preventDefault();

        if (!tagName.trim()) {
            setError('Tag name is required');
            return;
        }

        setAdding(true);
        setError(null);

        try {
            const timestampSeconds = timestamp ? parseFloat(timestamp) : null;
            const newTag = await tagApi.addTag(videoId, tagName.trim(), timestampSeconds);

            setTagName('');
            setTimestamp('');

            if (onTagAdded) {
                onTagAdded(newTag);
            }
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to add tag');
            console.error('Add tag error:', err);
        } finally {
            setAdding(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Add Manual Tag</h3>

            <form onSubmit={handleAddTag} className="space-y-4">
                <div>
                    <label htmlFor="tag-name" className="block text-sm font-medium text-gray-700 mb-1">
                        Tag Name *
                    </label>
                    <input
                        type="text"
                        id="tag-name"
                        value={tagName}
                        onChange={(e) => setTagName(e.target.value)}
                        placeholder="e.g., Armbar, Triangle, Guard Pass"
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        disabled={adding}
                    />
                    <p className="mt-1 text-xs text-gray-500">
                        Enter technique name, position, or any custom tag
                    </p>
                </div>

                <div>
                    <label htmlFor="timestamp" className="block text-sm font-medium text-gray-700 mb-1">
                        Timestamp (seconds)
                    </label>
                    <input
                        type="number"
                        id="timestamp"
                        value={timestamp}
                        onChange={(e) => setTimestamp(e.target.value)}
                        placeholder="e.g., 45.5"
                        step="0.1"
                        min="0"
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        disabled={adding}
                    />
                    <p className="mt-1 text-xs text-gray-500">
                        Optional: When does this technique appear in the video?
                    </p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={adding || !tagName.trim()}
                    className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded-lg transition-colors"
                >
                    {adding ? 'Adding...' : 'Add Tag'}
                </button>
            </form>

            <div className="mt-6 pt-6 border-t border-gray-200">
                <h4 className="text-sm font-semibold text-gray-600 mb-2">Common BJJ Tags</h4>
                <div className="flex flex-wrap gap-2">
                    {[
                        'Armbar',
                        'Triangle',
                        'Kimura',
                        'Rear Naked Choke',
                        'Guard Pass',
                        'Sweep',
                        'Mount',
                        'Back Control',
                        'Side Control',
                        'Half Guard',
                    ].map((suggestion) => (
                        <button
                            key={suggestion}
                            onClick={() => setTagName(suggestion)}
                            className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors"
                            type="button"
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default TagEditor;
