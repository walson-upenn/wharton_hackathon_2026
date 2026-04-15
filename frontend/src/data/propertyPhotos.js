export const PROPERTY_PHOTOS = {
  "9a0043fd": "https://plus.unsplash.com/premium_photo-1715954843149-84d682442e6a?q=80&w=2069&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
  "5f5a0cd8": "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8M3x8Z2VybWFueXxlbnwwfHwwfHx8MA%3D%3D",
  "e52d67a7": "https://images.unsplash.com/photo-1639647564912-651e29b8e6ad?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8YmFuZ2tvayUyMGhvdGVsfGVufDB8fDB8fHww",
  "3216b1b7": "https://images.unsplash.com/photo-1759431770496-c0147a6ad769?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OXx8YmVsbCUyMGdhcmRlbnN8ZW58MHx8MHx8fDA%3D",
  "db38b19b": "https://images.unsplash.com/photo-1634602417388-5dc691fecd4f?q=80&w=2678&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
  "ff26cdda": "https://plus.unsplash.com/premium_photo-1742457752636-f36ed3bb468a?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MTd8fGZyaXNjbyUyMHRleGFzfGVufDB8fDB8fHww",
  "a036cbe1": "https://images.unsplash.com/photo-1630215921793-dfbfd6d8bba7?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NHx8bWJvbWJlbGF8ZW58MHx8MHx8fDA%3D",
  "fa014137": "https://plus.unsplash.com/premium_photo-1675359655209-edb25475ce57?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8bW9udGVyZXl8ZW58MHx8MHx8fDA%3D",
  "f2d8d955": "https://images.unsplash.com/photo-1623008419825-05bcb221e5f4?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8M3x8bmV3JTIwc215cm5hJTIwYmVhY2h8ZW58MHx8MHx8fDA%3D",
  "7d027ef7": "https://plus.unsplash.com/premium_photo-1742457724078-669d91fc6ce3?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8b2NhbGF8ZW58MHx8MHx8fDA%3D",
  "110f01b8": "https://plus.unsplash.com/premium_photo-1661963222829-cf9572881843?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8OXx8cG9tcGVpfGVufDB8fDB8fHwwL",
  "823fb249": "https://plus.unsplash.com/premium_photo-1675975706513-9daba0ec12a8?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8cm9tZXxlbnwwfHwwfHx8MA%3D%3D",
  "3b984f3b": "https://plus.unsplash.com/premium_photo-1697730349278-a77281cd2c0f?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NXx8c2FuJTIwaXNpZHJvfGVufDB8fDB8fHww",
};

export const FALLBACK_PHOTO = "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800";

export function getPropertyPhoto(propertyId) {
  return PROPERTY_PHOTOS[propertyId?.slice(0, 8)] || FALLBACK_PHOTO;
}
