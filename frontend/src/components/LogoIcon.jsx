import React from 'react';

export default function LogoIcon({ size = 24, className = "", color = "currentColor" }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      width={size} 
      height={size} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke={color} 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      className={className}
    >
      {/* Database outline */}
      <path d="M4 6v12c0 2 8 3 16 0V6" />
      <ellipse cx="12" cy="6" rx="8" ry="3" />
      
      {/* Visual Chart Bars going up */}
      <line x1="8" y1="18.5" x2="8" y2="13" stroke="#22d3ee" strokeWidth="2.5" />
      <line x1="12" y1="19.5" x2="12" y2="8" stroke="#22d3ee" strokeWidth="2.5" />
      <line x1="16" y1="18.5" x2="16" y2="11" stroke="#22d3ee" strokeWidth="2.5" />
    </svg>
  );
}
