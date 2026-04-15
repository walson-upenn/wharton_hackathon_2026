const mockReviewSession = {
  reviewId: "review_123",
  property: {
    name: "Grand Hyatt New York",
    location: "New York, NY",
    stayRange: "Mar 28 – Mar 31, 2026",
  },
  stayUsageQuestion: {
    id: "stay_usage",
    label: "Which services or amenities did you use during your stay?",
    options: ["Breakfast", "Gym", "Pool", "Parking", "Wi-Fi", "Room service"],
  },
  questions: [
    {
      id: "q_overall",
      type: "rating",
      label: "How was your stay overall?",
      required: true,
    },
    {
      id: "q_1",
      type: "text",
      label: "What stood out most about your stay?",
      placeholder: "Tell us what stood out most",
      required: false,
    },
    {
      id: "q_2",
      type: "text",
      label: "Would you recommend this hotel to a friend? Why or why not?",
      placeholder: "Share a quick note",
      required: false,
    },
  ],
};

export default mockReviewSession;

