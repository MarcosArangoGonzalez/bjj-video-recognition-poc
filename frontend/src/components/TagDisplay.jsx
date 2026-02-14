import React from 'react';

const TagDisplay = ({ tags }) => {
    // Filter to show only BJJ-specific tags
    const bjjTags = tags.filter((tag) =>
        tag.tagName.startsWith('POSITION:') ||
        tag.tagName.startsWith('TECHNIQUE:') ||
        tag.tagName.startsWith('SUBMISSION:') ||
        tag.tagName.startsWith('SWEEP:') ||
        tag.tagName.startsWith('PASS:') ||
        tag.tagName.startsWith('TRANSITION:') ||
        tag.tagName.startsWith('TAKEDOWN:')
    );

    // Treat anything not MANUAL as AUTO (covering GEMINI, GEMINI_POSE, YOLO, AUTO, etc.)
    const autoTags = bjjTags.filter((tag) => tag.source !== 'MANUAL');
    const manualTags = tags.filter((tag) => tag.source === 'MANUAL');

    const formatTimestamp = (seconds) => {
        if (!seconds) return '';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const TagBadge = ({ tag, isAuto }) => (
        <div
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${isAuto
                ? 'bg-blue-100 text-blue-800 border border-blue-200'
                : 'bg-green-100 text-green-800 border border-green-200'
                }`}
        >
            <span className="font-medium">{tag.tagName}</span>
            {tag.confidence && (
                <span className="text-xs opacity-75">
                    {Math.round(tag.confidence * 100)}%
                </span>
            )}
            {tag.timestampSeconds !== null && tag.timestampSeconds !== undefined && (
                <span className="text-xs opacity-75">
                    {formatTimestamp(tag.timestampSeconds)}
                </span>
            )}
        </div>
    );

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Video Tags</h3>

            {tags.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No tags available</p>
            ) : (
                <div className="space-y-4">
                    {autoTags.length > 0 && (
                        <div>
                            <h4 className="text-sm font-semibold text-gray-600 mb-2 flex items-center gap-2">
                                <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                                    />
                                </svg>
                                Auto-Generated Tags
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {autoTags.map((tag) => (
                                    <TagBadge key={tag.id} tag={tag} isAuto={true} />
                                ))}
                            </div>
                        </div>
                    )}

                    {manualTags.length > 0 && (
                        <div>
                            <h4 className="text-sm font-semibold text-gray-600 mb-2 flex items-center gap-2">
                                <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                                    />
                                </svg>
                                Manual Tags
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {manualTags.map((tag) => (
                                    <TagBadge key={tag.id} tag={tag} isAuto={false} />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default TagDisplay;
