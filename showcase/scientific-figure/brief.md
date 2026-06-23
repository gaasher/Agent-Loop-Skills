# Figure brief (shared by the baseline and the loop runs)

Create a publication-quality **bar chart** showing the **single-crop top-1 ImageNet validation
accuracy** of landmark image-classification architectures, in **chronological order**, to illustrate the
progress of ImageNet classification. Each bar is one model; the y-axis is top-1 accuracy (%).

Models to include (chronological): **AlexNet (2012), VGG-16 (2014), GoogLeNet / Inception-v1 (2014),
ResNet-50 (2015), ResNet-152 (2015), DenseNet-201 (2017)**.

## Communication goal (the message)
A reader should see, at a glance, the upward march of **top-1** accuracy across architectures over time —
with the **metric stated unambiguously** (top-1, single-crop, ImageNet-1k validation) and every bar
height equal to the accuracy **as reported in that model's original paper**. Using a top-5 number where a
top-1 number belongs, or a misremembered value, is a substantive error.

## Style
Clean, modern, colorblind-safe, minimalist publication style. One bar per model in time order, value
labels on bars, a clear y-axis ("Top-1 accuracy (%)"), and a caption stating the metric and that values
are as reported in each original paper.
