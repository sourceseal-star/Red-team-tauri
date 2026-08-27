import React, { useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import '../../styles/index.css';

const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  className = ''
}) => {
  const handleEscape = useCallback((e) => {
    if (e.key === 'Escape' && onClose) {
      onClose();
    }
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'modal-sm',
    md: '',
    lg: 'modal-lg',
    xl: 'modal-xl'
  };

  const modalContent = (
    <div className={`modal-overlay ${className}`} onClick={onClose}>
      <div 
        className={`modal ${sizeClasses[size] || ''}`} 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          {title && <h5 className="modal-title">{title}</h5>}
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(
    modalContent,
    document.body
  );
};

export default Modal;
